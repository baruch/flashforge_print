#!/usr/bin/python3

import sys
import socket
import binascii

class FlashForgeSend(object):
    def __init__(self):
        self.s = None
        self.rxbuf = None

    def connect(self, hostname):
        self.s = socket.create_connection( (hostname, 8899) )
        self.rxbuf = None

    def send(self, data):
        if type(data) == str:
            data = data.encode('ascii')
        while len(data) > 0:
            count = self.s.send(data)
            if count == len(data):
                return
            data = data[count:]

    def read_all_lines(self):
        while True:
            self.wait_for_line()

    def wait_for_line(self):
        def check_buffer():
            if self.rxbuf is None: return None

            idx = self.rxbuf.find('\r\n'.encode('ascii'))
            if idx != -1:
                line = self.rxbuf[:idx+2]
                print('line found: %s' % line)
                self.rxbuf = self.rxbuf[idx+2:]
                return line

        ret = check_buffer()
        if ret is not None:
            return ret

        while True:
            tmp = self.s.recv(1024)
            print('received %d bytes' % len(tmp))
            if self.rxbuf is not None:
                self.rxbuf += tmp
            else:
                self.rxbuf = tmp
            ret = check_buffer()
            if ret is not None:
                return ret

    def wait_for_ack(self, cmd):
        line1 = self.wait_for_line()
        assert line1.find(('CMD %s' % cmd).encode('ascii')) != -1
        print ('line1 rcvd')
        while line1 != b'ok\r\n':
            line1 = self.wait_for_line()

    def encode_data(self, idx, chunk_data):
        crc_encode = binascii.crc32(chunk_data).to_bytes(4, byteorder='big', signed=False)
        orig_len = len(chunk_data)
        if len(chunk_data) < 4096:
            missing_len = 4096 - len(chunk_data)
            chunk_data = chunk_data + b'\0' * missing_len

        prefix = b'\x5a\x5a\xa5\xa5'
        idx_encode = idx.to_bytes(4, byteorder='big', signed=False)
        chunk_len_encode =  orig_len.to_bytes(4, byteorder='big', signed=False)

        encoded_data = prefix + idx_encode + chunk_len_encode + crc_encode + chunk_data
        assert len(encoded_data) == len(chunk_data) + 16
        return encoded_data

    def send_chunk(self, idx, chunk_data):
        encoded_data = self.encode_data(idx, chunk_data)
        self.send(encoded_data)
        line = self.wait_for_line()
        assert line.endswith(b'ok.\r\n')

    def send_file(self, file_data):
        self.send("~M28 %d 0:/user/ffdata.g\r\n" % len(file_data))
        self.wait_for_ack('M28')

        idx = 0
        while len(file_data) > 0:
            self.send_chunk(idx, file_data[0:4096])
            file_data = file_data[4096:]
            idx += 1

        self.send("~M29\r\n")
        self.wait_for_ack('M29')

        self.send("~M23 0:/usr/ffdata.g\r\n")
        self.wait_for_ack('M23')

    def close(self):
        self.s.close()
        self.rxbuf = None


if __name__ == '__main__':
    hostname = sys.argv[1]
    file_data = open(sys.argv[2], 'rb').read()

    f = FlashForgeSend()
    f.connect(hostname)
    f.send_file(file_data)
