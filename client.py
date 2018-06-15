# -*- coding:utf-8 -*-
import json
import sys
import socket

#从服务器接收一段字符串, 转化成字典的形式
def RecvJuderData(hSocket):
    nRet = -1
    Message = hSocket.recv(1024 * 1024 * 4)
    print(Message.decode())
    len_json = int(Message[:8])
    str_json = Message[8:].decode()
    while len(str_json)!=len_json:
        Message = hSocket.recv(1024 * 1024 * 4)
        str_json =str_json+Message.decode()
    if len(str_json) == len_json:
        nRet = 0
    Dict = json.loads(str_json)
    return nRet, Dict

# 接收一个字典,将其转换成json文件,并计算大小,发送至服务器
def SendJuderData(hSocket, dict_send):
    str_json = json.dumps(dict_send)
    len_json = str(len(str_json)).zfill(8)  #返回指定长度字符串，原字符串右对齐，前面填充0
    str_all = len_json + str_json
    ret = hSocket.sendall(str_all.encode())  #发送完整的TCP数据，成功返回None  失败抛出异常
    if ret == None:
        ret = 0
    # print('发送结果（0表示正确）:', ret)
    return ret         #0表示正常、
#以下更改为便于打印测试，最终提交需删除
def RecvJuderData1(hSocket):
    nRet = -1
    Message = hSocket.recv(1024 * 1024 * 4)
    # print(Message.decode())
    len_json = int(Message[:8])
    str_json = Message[8:].decode()
    while len(str_json)!=len_json:
        Message = hSocket.recv(1024 * 1024 * 4)
        str_json =str_json+Message.decode()
    if len(str_json) == len_json:
        nRet = 0
    Dict = json.loads(str_json)
    # print("time=%d时，对方无人机1:"%(Dict['time']))
    # for i in range(len(Dict['UAV_enemy'])):
    #     print(Dict['UAV_enemy'][i])
    # print("time=%d时，返回货物信息:" % (Dict['time']))
    # for i in range(len(Dict['goods'])):
    #     print(Dict['goods'][i])
    return nRet, Dict

# 接收一个字典,将其转换成json文件,并计算大小,发送至服务器
def SendJuderData1(hSocket, dict_send):
    str_json = json.dumps(dict_send)
    len_json = str(len(str_json)).zfill(8)  #返回指定长度字符串，原字符串右对齐，前面填充0
    str_all = len_json + str_json
    # print(str_all)
    # print('我方无人机：')
    # for i in range(len(dict_send['UAV_info'])):
    #     print(dict_send['UAV_info'][i])
    ret = hSocket.sendall(str_all.encode())  #发送完整的TCP数据，成功返回None  失败抛出异常
    if ret == None:
        ret = 0
    # print('发送结果（0表示正确）:', ret)
    return ret         #0表示正常