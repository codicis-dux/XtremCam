# -*- coding: UTF-8 -*-
#--------------------------------------------------------------------------------------------------
# Name:        XtremCam4win
# Version:     1.00
# Purpose:     Action/sport WiFi 4K camera monitor for ®Microsoft Windows
#               => WiFi video preview
# Author:      ÐR
# Created:     08/02/2023
# Copyright:   (c)2023 - Didier Rius
# Licence:     Creative Commons(CC BY-NC-SA 4.0) applies to the whole work or any part of the code.
#              This work is licensed under Attribution-NonCommercial-ShareAlike 4.0 International.
#              To view a copy of this license : http://creativecommons.org/licenses/by-nc-sa/4.0/
# Disclaimer:  The softwre is provided "as is", without warranty of any kind.-use at your own risk-
#--------------------------------------------------------------------------------------------------

import os, platform, socket, cv2, sys
import win32pipe as wp, win32file as wf
from multiprocessing import Process, Value
from contextlib import contextmanager
from time import sleep


def camlogging(fsuccess):
    camip = '192.168.100.1'
    hostip ='192.168.100.105'
    camport = 6666
    camlogged = False
    cred = bytearray(137)
    cred[0:13]= b'\xab\xcd\x00\x81\x00\x00\x01\x10\x61\x64\x6d\x69\x6e'
    cred[72:77]= b'\x31\x32\x33\x34\x35'
    keeponrunning_com = b'\xab\xcd\x00\x00\x00\x00\x01\x13'
    getstream_com = b'\xab\xcd\x00\x08\x00\x00\x01\xff\x00\x00\x00\x00\x00\x00\x00\x00'
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        tcp.connect((camip, camport))
    except socket.error as err:
        print("Error :", err.strerror)
        print('\tCheck device connection.')
        exit(1)
    while True:
        try: data = tcp.recv(256)
        except: break
        if data[7] ==  18:
            if (not camlogged): tcp.sendall(cred)
            else: tcp.sendall(keeponrunning_com)
        if (data[7] ==  17):
            fsuccess.value = camlogged = True
            tcp.sendall(getstream_com)
    tcp.close()


def videoReader(pipename):
    cap = cv2.VideoCapture(pipename, 1900)       # cv2.CAP_FFMPEG /h264
    print('\tVideo capture : fps', cap.get(cv2.CAP_PROP_FPS))
    quitmsg = ' - Hit any key to quit'
    wname = "Video - {} x {}".format(int(cap.get(3)), int(cap.get(4))) + quitmsg

    while cap.isOpened():
        ret, frame = cap.read()
        if ret: cv2.imshow(wname, frame)
        if cv2.waitKey(1) > 1 : break
    sys.stderr.flush()
    cap.release()
    cv2.destroyAllWindows()
    print('\tvideoReader is over.')


def streamXceiver(pipename: str, fsuccess):
    udprecv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) # UDP
    udprecv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ##    udprecv.settimeout(8)
    hostip = '192.168.100.105'
    udprecv.bind((hostip, 6669))
    hpipe = wp.CreateNamedPipe(pipename, wp.PIPE_ACCESS_OUTBOUND,         # PIPE_ACCESS_DUPLEX
                                wp.PIPE_TYPE_BYTE | wp.PIPE_READMODE_BYTE | wp.PIPE_WAIT,
                                1, 65536, 65536, 300, None)
    data, addr = udprecv.recvfrom(1024)
    fsuccess.value = True
    wp.ConnectNamedPipe(hpipe)
    # Start : .......................................................................................................
    data, addr = udprecv.recvfrom(1024)
    # synchro starting frame :
    while data[7] < 5: data, addr = udprecv.recvfrom(1024)
    # send frame stream :
    while data[7] :
        data, addr = udprecv.recvfrom(1024)
        if data[7] == 1: err, bytes_written = wf.WriteFile(hpipe, data[8:])


@contextmanager
def catch_stdstream(nse):    # redirect stderr
    stdstream_no = 2         # stdstream_no = sys.stderr.fileno() = 2 (stdout = 1)
    with os.fdopen(os.dup(stdstream_no), 'w') as dupfd:
        os.dup2(nse.fileno(), stdstream_no)
        yield
        os.dup2(dupfd.fileno(), stdstream_no)


def main():
    pipe = r'\\.\pipe\streamPipe'
    fsuccess = Value('B', False)
    logfile = os.devnull
    if len(sys.argv) > 1 :
        print('codec errors will be logged in log.txt file.')
        logfile = 'log.txt'
    cmlog_p = Process(target=camlogging, args=(fsuccess,))
    print('\tConnecting...')
    cmlog_p.start()
    while not fsuccess.value:
        if cmlog_p.exitcode: exit(1)
        sleep(0.1)
    fsuccess.value = False
    print('\tStarting videostream relay...')
    Xcvr_p = Process(target=streamXceiver, args=(pipe, fsuccess,))
    Xcvr_p.start()
    while not fsuccess.value: sleep(0.1)
    print('\t\tStarting video capture...soon...')
    with open(logfile, 'w') as newstdout, catch_stdstream(newstdout):
        videoReader(pipe)
    Xcvr_p.kill()
    cmlog_p.kill()
    print('Process closed.')


if __name__ == '__main__':
    print('\tXtremCam4win v1.0 - ©2022-2023 Ð.Rius\n')
    print ('Local host System version : os', os.name, platform.system(), platform.release())
    print('Local host Python version :', platform.python_version())
    # print("Version info :", sys.version_info)
    print ('Local host opencv version :', cv2.__version__)
    main()

####