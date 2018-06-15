# -*- coding:utf-8 -*-
import sys
import socket
import json
import copy
import numpy as np
from game_functions import *
import time
import logging
from client import *
from step import *
from Charge import *

def sortValue(t):  #对UAV_price列表按照value从小到大排序，一个字典代表一个文人机价格
    return t['value']
def sortLW(t):     #对UAV_enemy列表按照load_weight从大到小排序
    return t['load_weight']
def main(szIp, nPort, szToken):
    print("server ip %s, prot %d, token %s\n"%(szIp, nPort, szToken))
    #Need Test // 开始连接服务器
    hSocket = socket.socket()
    hSocket.connect((szIp, nPort))
    #接受数据  连接成功后，Judger会返回一条消息：
    nRet, _ = RecvJuderData(hSocket)  #nRet位0表示接收正常
    if (nRet != 0):
        return nRet
    # // 生成表明身份的json
    token = {}
    token['token'] = szToken        
    token['action'] = "sendtoken"
    #// 选手向裁判服务器表明身份(Player -> Judger)
    nRet = SendJuderData(hSocket, token)
    if nRet != 0:
        return nRet
    #//身份验证结果(Judger -> Player), 返回字典Message
    nRet, Message = RecvJuderData(hSocket)
    if nRet != 0:
        return nRet
    if Message["result"] != 0:
        print("token check error\n")
        return -1
    # // 选手向裁判服务器表明自己已准备就绪(Player -> Judger)
    stReady = {}
    stReady['token'] = szToken
    stReady['action'] = "ready"
    nRet = SendJuderData(hSocket, stReady)
    if nRet != 0:
        return nRet
###############################################对战开始########################################
    # //对战开始通知(Judger -> Player)
    nRet, Message = RecvJuderData(hSocket)        #接受地图  time=0
    if nRet != 0:
        return nRet
    #初始化地图信息
    MapInfo = Message["map"]

    # print('UAV_price')
    # for i in MapInfo['UAV_price']:
    #     print(i)
    # print('init_UAV')
    # for i in MapInfo['init_UAV']:
    #     print(i)

    map_grid = MapBuild(MapInfo['map']['x'], MapInfo['map']['y'], MapInfo['map']['z'], MapInfo['building'], MapInfo['parking'], MapInfo['fog'])
    Fnum_lw = TypeLoad(MapInfo['UAV_price']) #{'F1':100,'F2':50...}  TYPE:load_weight
    Fnum_value = TypeValue(MapInfo['UAV_price'])  #{'F1':300...}  TYEP:VALUE
    Fnum_capacity, Fnum_charge = TypeCapacityCharge(MapInfo['UAV_price'])  #返回TYPE:CAPACITY  TYPE:CHARGE字典

    mystart = [MapInfo['parking']['x'],MapInfo['parking']['y']]  #我方停机坪

    enemyno_goodsno ={}  #对方无人机坠毁就不会出现在UAV_enemy，更正上方，只记录status=0/2的编号和goods_no编号
    #购买无人机使用
    Ftype_num = {}  #{'F1':2,}   myFly中已存在的无人机种类和其数量
    UAV_price = sorted(MapInfo['UAV_price'], key=sortValue)  #列表，元素为字典类型，同UAV_price,按照价值从小到大排序

    #按照value从小到大排列
    h_low = MapInfo['h_low']
    h_high = MapInfo['h_high']
    floor = {}  #存放对应编号的无人机对应的目标层
    high_low=h_high-h_low+1
    if high_low>3:
        high_low=3

    #初始化比赛状态信息
    fromJ = {}                 #用来存放每一步服务器返回的
    fromJ["time"] = 0
    #实时无人机、目标记录，路径， 变化则更新
    myFly = []  #每个字典元素代表一个无人机，格式同init_UAV 全局 #只保留活着的
    goalGood = []  #有则为一条货物记录，无则为0,和无人机no标号对应
    closes_F = []  #每个列表元素对应一个无人机，记录走过的格子横纵坐标点  三层列表
    closes_P = []
    steplen_P =[]  #防止阶段根据此值判断上升和下降
    position = []  #记录myFly中每个无人机的当前位置，和无人机no标号对应  三维点，下同
    position_L = [] #记录myFly中每个无人机的上一时刻位置，和无人机no标号对应
    flag_up = [] #记录空载低于目标层时是上升和 下降，1表示上升，0表示下降

    apron_state = 1   #记录停机坪通道使用状态，0表示通道无机，1表示通道上升
    goodspath = {}  #记录每个货物编号和对应几层的起点到终点的二维路径点
    queue_charge = []  #排队充电的我方无人机列表，存放'no'
    queue = []  #回坪点最后四步之前

    stack_atts = []  #蹲守对方停机坪的无人机堆栈  编号
    stack_F3 = []   #被F3追踪的敌机名单，no
    StaticEnes = {}  #蹲守我方投放点的敌机编号和三维点字典元素

    #每一步的飞行计划
    toJ = {}     #player->judger 无人机坐标信息
    toJ["token"] = szToken
    toJ["action"] = "flyPlane"

    for i in range(len(MapInfo["init_UAV"])):
        myFly.append(MapInfo['init_UAV'][i])
        goalGood.append(0)
        closes_F.append([])
        closes_P.append([])
        steplen_P.append(0)   #初始走过的步长
        floor[MapInfo['init_UAV'][i]['no']]=MapInfo['init_UAV'][i]['no'] % (high_low) + h_low   #{0:7,1:8,2:9,3:7} 初始化无人机数据，后面需要更新
        flag_up.append(1)
        if MapInfo['init_UAV'][i]['type'] in Ftype_num.keys():  #若果已存在则加一个，否则赋值为1，myFly中无人机
            Ftype_num[MapInfo['init_UAV'][i]['type']]+=1
        else:
            Ftype_num[MapInfo['init_UAV'][i]['type']]=1
        enemyno_goodsno[i]=-1  #初始化对方和我方无人机完全相同
    myFly = sorted(myFly, key=my_no)  #no=0,1,2,3....
    for i in range(len(myFly)):
        position.append(None)
        position_L.append([myFly[i]['x'],myFly[i]['y'],myFly[i]['z']])
        del myFly[i]['load_weight']
    FlyPlane = copy.deepcopy(myFly)
    for i in FlyPlane:
        del i['type'];del i['status']
    toJ['UAV_info'] = FlyPlane
    print('time:%d'%(fromJ['time']))
    nRet = SendJuderData(hSocket, toJ)  # Player -> Judgerb  第一步发送0时刻位置 还没移动
    if nRet != 0:
        return nRet
    while True:
        nRet, fromJ = RecvJuderData1(hSocket)  # Judger -> Player  从time=1开始询问位置
        if nRet != 0:
            return nRet
        tic = time.time()
        enemyno_positionN = No_positN(fromJ['UAV_enemy']) #记录当前对方无人机编号和对应位置  enemyno_positionL为敌机上一课位置，判断不动
        gNo_position= Goods_NoPosit(fromJ['goods'],h_low)  #所有货物no:[end_x,end_y]字典
        goods_nosta, goods_noleft =GoodStatus(fromJ) #实时更新货物编号和对应状态，返回键值对字典  货物没了会被删除  #货物编号和剩余时间
        GoodsPath(map_grid,fromJ['goods'],high_low,h_low,goodspath,gNo_position)  #更新goodspath
        UAVene_sort = sorted(fromJ['UAV_enemy'], key=sortLW,reverse=True)  #从大到小
        enemyUpdate(stack_F3, enemyno_positionN)  #更新stack——F3
        if fromJ['time']>2:
            StaticUpdate(StaticEnes,enemyno_positionN,enemyno_positionL)  #删除StaticEnes中需要删除的
        # if len(StaticEnes)!=0:
        #     for k,v in StaticEnes.items():                     #更新StaticEnes，如果坠毁则删除  #
        #         if k not in enemyno_positionN.keys():#该机坠毁
        #             del StaticEnes[k]


# 更新myFly相关
        myFlyUpdate(fromJ['UAV_we'], myFly, goalGood, position, position_L, closes_F, closes_P, Ftype_num, steplen_P,
                    floor, flag_up, high_low, h_low, queue_charge,stack_atts)
        numap = ApronFlys(myFly, Fnum_capacity, mystart,h_high,UAV_price)  #统计我方充满电后在停机坪通道上的数量
        enemymenu, goodsAtt, goodsLoad = Confirm(goalGood, myFly, UAV_price)  # 目标机、战机锁定的货物、货机锁定的货物

        if numap>0 or len(queue_charge)==0:  #没有排队充电的无人机  #以出为主
            apron_state=1  #1表示用于出
        else:                                #充电队列中有需要回坪的则更改为回用状态
            apron_state=0  #0表示用于回
        #
        # print('货物编号：对应%d层的路径：'%high_low)
        # for k,v in goodspath.items():
        #     print('货物编号为：%d'%k)
        #     for i in range(high_low):
        #         print(v[i])
        # print('目标货物：')
        # for i in goalGood:
        #     print(i)
        # print('静止敌机：')
        # print(StaticEnes)
        # print('蹲守对方停机坪的列表：')
        # print(stack_atts)
        # print('通道状态1出，0回：%d'%apron_state)
        # print('等待进入停机坪通道充电：')
        # if len(queue_charge)!=0:
        #     for i in queue_charge:
        #         print(i)
        # print('我方无人机位置列表：')
        # for i in range(len(myFly)):
        #     print(myFly[i]['status'],position[i])
        # print('F3的追踪目标列表:')
        # for i in stack_F3:
        #     print(i)
        if fromJ['time']==1:
            enemy_apron = EnemyApron(fromJ['UAV_enemy'])  #对手二维停机坪坐标列表
        # enesinapron = EnyApronCNT(fromJ['UAV_enemy'], enemy_apron)  #对方在停机坪中的数量

#第一步，更新无人机位置，根据closes_P,closes_F,goalGood
        for i in range(len(myFly)):  # 每个无人机开始遍历
                if myFly[i]['status'] == 1:  # 坠毁不考虑
                    continue
#不充电的廉价机F3，跟踪对方最大机，
                # if myFly[i]['remain_electricity']==0 and myFly[i]['type']==UAV_price[0]['type']:#F3不经过充电直接出坪
                #     if myFly[i]['z']<h_low:
                #         # if [myFly[i]['x'], myFly[i]['y'], myFly[i]['z'] +1] in position:  # 下方有我方无人机，则不动
                #         #     continue
                #         myFly[i]['z']+=1
                #         # position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                #         continue
                #     if goalGood[i]!=0 and goalGood[i]['no'] not in stack_F3:#目标机坠毁需要将其变为0
                #         goalGood[i]=0
                #     if goalGood[i]==0:
                #         goalGood[i] = AttackTargetF3(UAVene_sort,myFly[i],h_low,stack_F3)  #分配一个不再雾区的追踪对象
                #         if goalGood[i]!=0 and goalGood[i] not in stack_F3:
                #             stack_F3.append(goalGood[i]['no'])   #追踪列表
                #         else:
                #             #没有目标机则随机漫步
                #             RandomStep(MapInfo, map_grid, myFly[i], position, position_L, fromJ['UAV_enemy'],Fnum_value)  # 随机水平移动一步,无撞机    #出现了交叉撞机
                #             position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                #             continue
                #     if goalGood[i]!=0 and myFly[i]['z']==h_low:
                #         if [goalGood[i]['x'],goalGood[i]['y']]!=[-1,-1]:#对方未进入雾区
                #             goal = [goalGood[i]['x'],goalGood[i]['y']]  #当前目标敌机位置
                #         if [myFly[i]['x'],myFly[i]['y']] ==goal:#到达目标点
                #             continue
                #         else:
                #             HoriAtt(MapInfo,map_grid,myFly[i],goal,closes_F[i],position,position_L,fromJ['UAV_enemy'], Fnum_value)  #躲开了价值小于等于的，不合理需要改
                #             a = [myFly[i]['x'], myFly[i]['y']]
                #             if a not in closes_F[i]:
                #                 closes_F[i].append(a)
                #             position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                #             continue

#堆栈中的战机（带电）先处理，加入则视死如归  #此部分为廉价机无目标加入蹲守对方停机坪
                if myFly[i]['no'] in stack_atts:
                    if [myFly[i]['x'], myFly[i]['y'], myFly[i]['z'] - 1] in position or myFly[i]['z']==1:  # 下方有我方无人机，或已经下降到最低位
                        continue
                    myFly[i]['z']-=1
                    position[i]=[myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
                    continue
#充电桩内处理  #对于战机，如果可直接出则不充电，否则充电
                if  [myFly[i]['x'], myFly[i]['y']] == mystart and myFly[i]['z']==0:#在坪中,充电
                    if apron_state ==1 and myFly[i]['remain_electricity']==0 and myFly[i]['type']==UAV_price[0]['type']: #战机直接出,不充电在停机坪中待验证:不可以
                        OutArra(myFly[i], position)
                        if myFly[i]['z']!=0:#上面没有无人机，才出坪记录位置
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
                        else:
                            charge(myFly[i], Fnum_capacity, Fnum_charge)
                        continue
                    if apron_state == 0 or myFly[i]['remain_electricity'] < Fnum_capacity[myFly[i]['type']]:  # 回坪状态，或没充满 不动
                        charge(myFly[i], Fnum_capacity, Fnum_charge)
                        continue
                    if apron_state==1 and myFly[i]['remain_electricity'] == Fnum_capacity[myFly[i]['type']]:  # 已充满，准备出坪  #此处必须先充满，下一步才能出坪
                        OutArra(myFly[i], position)
                        if myFly[i]['z']!=0:#上面没有无人机，才出坪记录位置
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
                        continue
#处理充电桩通道上的无人机
                if apron_state==1:  #停机坪通道为出状态，上升
                    if [myFly[i]['x'], myFly[i]['y']] == mystart:
                        if myFly[i]['remain_electricity']==0 and myFly[i]['z'] < h_low:#战机
                            OutArra(myFly[i], position)
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
                            continue
                        if myFly[i]['z'] < floor[myFly[i]['no']] and myFly[i]['remain_electricity']!=0: #充电了的上升一步
                            OutArra(myFly[i], position)
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
                            continue
                else:               #停机坪通道为回状态
                    if myFly[i]['no'] in queue_charge:  #回坪通道开启后队列中无人机向坪移动,距离停机坪上方三步则压入队列
                        if [myFly[i]['x'], myFly[i]['y']] == mystart and myFly[i]['z'] == floor[myFly[i]['no']]:
                            if [myFly[i]['x'], myFly[i]['y'], myFly[i]['z'] - 1] in position:  # 下方有我方无人机，则不动
                                continue
                            else:
                                myFly[i]['z']-=1
                                position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
                                continue
                        if [myFly[i]['x'], myFly[i]['y']] != mystart and myFly[i]['z'] == floor[myFly[i]['no']]: #回坪尾程水平
                            HoriAtt(MapInfo, map_grid, myFly[i], mystart, closes_F[i], position, position_L,fromJ['UAV_enemy'], Fnum_value)  # 向对方停机坪水平移动一步
                            a = [myFly[i]['x'], myFly[i]['y']]
                            closes_F[i].append(a)
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                            continue
                        if [myFly[i]['x'], myFly[i]['y']] == mystart and myFly[i]['z']<floor[myFly[i]['no']]:#回坪下降
                            InArra(myFly[i], position)
                            if myFly[i]['z']==0:
                                charge(myFly[i], Fnum_capacity, Fnum_charge)
                                position[i] = None  # 此处需要清空位置
                                closes_F[i].clear()
                                goalGood[i]=0
                                if myFly[i]['no'] in queue_charge:  # 到达停机坪则从队列中删除
                                    queue_charge.remove(myFly[i]['no'])
                                continue
                            else:
                                position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  #停机坪位置不记录
                                continue
# # 停机坪位置的无人机移动,出坪
#                 if [myFly[i]['x'], myFly[i]['y']] == mystart and apron_state == 1:  # 处于停机坪位置,充电/出坪，
#                     if myFly[i]['z'] == floor[myFly[i]['no']]:
#                         RandomStep(MapInfo, map_grid, myFly[i], position, position_L, fromJ['UAV_enemy'], Fnum_value)  # 随机移动一步，无撞机
#                         position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第j个无人机位置改变
#                         continue
#                     elif myFly[i]['remain_electricity'] == Fnum_capacity[myFly[i]['type']]:  # 已充满，准备出坪
#                         OutArra(myFly[i], position)
#                         position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
#                         continue
#                     else:
#                         charge(myFly[i], Fnum_capacity, Fnum_charge)
#                         continue

#战机到达对方停机坪上方
                # if myFly[i]['x']==enemy_apron[0] and myFly[i]['y']==enemy_apron[1] and myFly[i]['no'] in stack_atts:  #到达对方停机坪上方且无目标物体，则下降
                #     if [myFly[i]['x'], myFly[i]['y'],myFly[i]['z'] - 1] in position:  # 下方有我方无人机，则不动
                #         continue
                #     if myFly[i]['z']==1:
                #         continue
                #     myFly[i]['z']-=1  #下降一步
                #     position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                #     continue

# 先更新goalGood

#战机到达目标层,战机处理部分，战机仅执行到此
                if myFly[i]['remain_electricity']==0 and myFly[i]['type']==UAV_price[0]['type'] and myFly[i]['z']==h_low:#F3 已经到达h_low
                    # if myFly[i]['z']<h_low:
                    #     if [myFly[i]['x'], myFly[i]['y'], myFly[i]['z'] +1] in position:  # 下方有我方无人机，则不动
                    #         continue
                    #     myFly[i]['z']+=1
                    #     position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                    #     continue
                    if goalGood[i]!=0 and 'type' in goalGood[i].keys() and goalGood[i]['no'] not in stack_F3:#目标机坠毁需要将其变为0
                        goalGood[i]=0
                        closes_F[i].clear()  #水平移动路径清空
                    if goalGood[i]==0 or 'weight' in goalGood[i].keys():  #优先分配目标机
                        target = AttackTargetF3(UAVene_sort,myFly[i],h_low,stack_F3,Fnum_value)  #分配一个不再雾区的追踪对象
                        if target !=0:  #分到目标机才改变,否则不变
                            goalGood[i]=target
                        elif len(StaticEnes)!=0:#有静止敌机
                            t = StaticAtt(StaticEnes, myFly[i], fromJ['UAV_enemy'], stack_F3, h_low)  # 此处格式统yi，分配静止机
                            if t!=0:#分到了静止敌机
                                goalGood[i]=t  #格式同UAV_enemy

                        if goalGood[i]!=0 and 'type' in goalGood[i].keys() and goalGood[i]['no'] not in stack_F3: #目标机
                            stack_F3.append(goalGood[i]['no'])   #追踪列表
                        # if goalGood[i]==0 and len(StaticEnes)!=0:   #没有目标优先分配静止敌机，有静止敌机
                        #     goalGood[i] = StaticAtt(StaticEnes, myFly[i], ['UAV_enemy'], stack_F3, h_low)   #此处格式统yi
                        if goalGood[i]==0 :  #没有目标则去追未被我方定位的最大价值货物
                            goalGood[i]= MaxLoadAtt(goodsLoad,goodsAtt,fromJ)
                            # #没有目标机则随机漫步
                            # RandomStepAtt(MapInfo, map_grid, myFly[i], position, position_L, fromJ['UAV_enemy'],Fnum_value,h_low,myFly,UAV_price)  # 随机水平移动一步,无撞机    #出现了交叉撞机
                            # position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                            # continue
                    if goalGood==0:  #都没分配到，随机走一步
                        RandomStep(MapInfo, map_grid, myFly[i], position, position_L, fromJ['UAV_enemy'],Fnum_value)  # 随机水平移动一步,无撞机    #出现了交叉撞机
                        position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                        continue
                        # RandomStepAtt(MapInfo, map_grid, myFly[i], position, position_L, fromJ['UAV_enemy'], Fnum_value,
                        #               h_low, myFly, UAV_price)  # 随机水平移动一步,无撞机    #出现了交叉撞机
                        # position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                        # continue
                    if goalGood[i]!=0 and 'weight' in goalGood[i].keys(): #目标货物移动方案  #必须保证我方定位此物体后释放
                        if goalGood[i]['no'] in goodsLoad or goalGood[i]['no'] not in goods_noleft.keys() or goods_noleft[goalGood[i]['no']]<=h_low:   #被货机绑定或者货物消失,放弃此目标物随机移动一步
                            goalGood[i]=0
                            closes_F[i].clear()
                            RandomStep(MapInfo, map_grid, myFly[i], position, position_L, fromJ['UAV_enemy'],
                                       Fnum_value)  # 随机水平移动一步,无撞机
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                            continue
                        if [myFly[i]['x'],myFly[i]['y']]==[goalGood[i]['start_x'],goalGood[i]['start_y']]:
                            continue
                        else:
                            HoriAtt(MapInfo, map_grid, myFly[i], [goalGood[i]['start_x'],goalGood[i]['start_y']], closes_F[i], position, position_L,fromJ['UAV_enemy'], Fnum_value)  # 躲开了价值小于等于的，不合理需要改
                            a = [myFly[i]['x'], myFly[i]['y']]
                            if a not in closes_F[i]:
                                closes_F[i].append(a)
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                            continue
                    if goalGood[i]!=0 and goalGood[i]['no'] in StaticEnes.keys():  #目标为蹲守的战机，不包括雾区中的
                        if [myFly[i]['x'],myFly[i]['y']] == [StaticEnes[goalGood[i]['no']][0],StaticEnes[goalGood[i]['no']][1]]:
                            if myFly[i]['z']<StaticEnes[goalGood[i]['no']][2]:
                                myFly[i]['z']+=1
                                position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
                                continue
                            elif myFly[i]['z']>StaticEnes[goalGood[i]['no']][2]:
                                myFly[i]['z']-=1
                                position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
                                continue
                        else:
                            pos = [StaticEnes[goalGood[i]['no']][0],StaticEnes[goalGood[i]['no']][1]]   #静止机二维点
                            HoriAtt(MapInfo, map_grid, myFly[i], pos, closes_F[i], position, position_L,fromJ['UAV_enemy'], Fnum_value)  # 躲开了价值小于等于的，不合理需要改
                            a = [myFly[i]['x'], myFly[i]['y']]
                            if a not in closes_F[i]:
                                closes_F[i].append(a)
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                            continue
                    if goalGood[i]!=0 and 'type' in goalGood[i].keys(): #目标机移动方案
                        if [enemyno_positionN[goalGood[i]['no']][0],enemyno_positionN[goalGood[i]['no']][1]]!=[-1,-1]:#对方未进入雾区
                            goal = [enemyno_positionN[goalGood[i]['no']][0],enemyno_positionN[goalGood[i]['no']][1]]  #当前目标敌机位置
                            # print('第%d个无人机的目标位置为：'%i)
                            # print(goal)
                        if [myFly[i]['x'],myFly[i]['y']] ==goal:#到达目标点,进入雾区则不动
                            continue
                        else:
                            HoriAtt(MapInfo,map_grid,myFly[i],goal,closes_F[i],position,position_L,fromJ['UAV_enemy'], Fnum_value)  #躲开了价值小于等于的，不合理需要改
                            a = [myFly[i]['x'], myFly[i]['y']]
                            if a not in closes_F[i]:
                                closes_F[i].append(a)
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                            continue
# 清理静止机的z轴方向追踪单独处理
                if myFly[i]['remain_electricity'] == 0 and myFly[i]['type'] == UAV_price[0]['type'] and myFly[i]['z'] != h_low:
                    if goalGood[i] != 0 and goalGood[i]['no'] in StaticEnes.keys():  # 目标为蹲守的战机，不包括雾区中的
                        if [myFly[i]['x'], myFly[i]['y']] == [StaticEnes[goalGood[i]['no']][0],StaticEnes[goalGood[i]['no']][1]]:
                            if myFly[i]['z'] < StaticEnes[goalGood[i]['no']][2]:
                                myFly[i]['z'] += 1
                                position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
                                continue
                            elif myFly[i]['z'] > StaticEnes[goalGood[i]['no']][2]:
                                myFly[i]['z'] -= 1
                                position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
                                continue
                    else:   #z轴方向跟踪过程中目标机丢失
                        goalGood[i]=0
                        if myFly[i]['z']>h_low:
                            if [myFly[i]['x'], myFly[i]['y'], myFly[i]['z'] - 1] in position:  # 下方有我方无人机，则不动
                                continue
                            myFly[i]['z']-=1
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
                            continue
                        if myFly[i]['z']<h_low:
                            if [myFly[i]['x'], myFly[i]['y'], myFly[i]['z'] + 1] in position:  # 下方有我方无人机，则不动
                                continue
                            myFly[i]['z']+=1
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
                            continue
# 表示尚无目标物或者已经分配了敌机！
                if goalGood[i] == 0 or ('goalP' in goalGood[i].keys()):
                    myload_dict, cnt_queue= MaxLoad(fromJ, myFly[i], goalGood, Fnum_lw, floor, goodspath,h_low, goodsAtt)
                    if myload_dict=={} and cnt_queue!=0 and  myFly[i]['no'] not in queue:  #由于电量没分配到货物，加入待充电队列,只加入一次
                        queue.append(myFly[i]['no'])
                    if myload_dict != {}:  # 找到目标货物则赋值目标货物字典，否则不变
                        goalGood[i] = myload_dict
                        if myFly[i]['no'] in queue:
                            queue.remove(myFly[i]['no'])

# 到达目标层但无目标物则分配目标机
                if goalGood[i] == 0 and myFly[i]['z'] == floor[myFly[i]['no']]:  # 优先分配货物，没分到货物分敌机
                    goalGood[i] = AttackTarget(fromJ['UAV_enemy'], Fnum_value, myFly[i], h_low, gNo_position,enemyno_goodsno, goalGood,stack_F3)  # 分配敌机和目标点 goalGood格式改变了，不再是goods记录格式
                    if goalGood[i] == 0 and myFly[i]['type']==UAV_price[0]['type']:  # 分配失败,廉价机则压入蹲守停机坪栈，仅压入一次，廉价机不充电
                        if myFly[i]['no'] in queue:  #回坪充电前部分
                            queue.remove(myFly[i]['no'])
                        #分配货物和蹲守的目标机失败，则追踪静止的对方蹲守机

                        if DisApronEne(myFly[i],enemy_apron)<3:     #至此则加入蹲守停机坪。不再分配货物和目标机
                            # if len(stack_atts)<enesinapron and len(stack_atts)<(h_low-2):  #此部分值只负责加入堆栈，堆栈中敌机均低于目标层且在对上停机坪上方
                            # if myFly[i]['no'] not in stack_atts:
                            #     stack_atts.append(myFly[i]['no'])
                            if len(stack_atts) < (h_low//2):  #解决不下降到停机坪堆积不动问题
                                if [myFly[i]['x'], myFly[i]['y']] == enemy_apron:  #最后几步移向对方停机坪
                                    if [myFly[i]['x'], myFly[i]['y'],myFly[i]['z'] - 1] in position:  # 下方有我方无人机，则不动
                                        continue
                                    myFly[i]['z']-=1
                                    position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                                    if myFly[i]['no'] not in stack_atts:   #加入堆栈，不再分配，视死如归
                                        stack_atts.append(myFly[i]['no'])
                                    continue
                                else:
                                    HoriAtt(MapInfo, map_grid, myFly[i], enemy_apron, closes_F[i], position, position_L,fromJ['UAV_enemy'], Fnum_value)  # 向对方停机坪水平移动一步
                                    a = [myFly[i]['x'], myFly[i]['y']]
                                    closes_F[i].append(a)
                                    position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                                    continue
                            else:
                                RandomStep(MapInfo, map_grid, myFly[i], position, position_L, fromJ['UAV_enemy'],Fnum_value)  # 随机水平移动一步,无撞机    #出现了交叉撞机
                                position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                                continue
                        else:
                            HoriAtt(MapInfo, map_grid, myFly[i], enemy_apron, closes_F[i], position, position_L,fromJ['UAV_enemy'], Fnum_value) #向对方停机坪水平移动一步
                            a = [myFly[i]['x'], myFly[i]['y']]
                            closes_F[i].append(a)
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                            continue
                        # else:
                        # RandomStep(MapInfo, map_grid, myFly[i], position, position_L, fromJ['UAV_enemy'],Fnum_value)  # 随机水平移动一步,无撞机    #出现了交叉撞机
                        # position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                        # continue
                    if goalGood[i]==0 and myFly[i]['type']!=UAV_price[0]['type'] and myFly[i]['no'] not in queue: #不是因为电量而没分配到货物
                        # if max(abs(myFly[i]['x']-mystart[0]), abs(myFly[i]['y']-mystart[1]))>4:  # 距离水平回坪点4步时加入队列
                        #     HoriAtt(MapInfo, map_grid, myFly[i], mystart, closes_F[i], position, position_L,fromJ['UAV_enemy'], Fnum_value)  # 向对方停机坪水平移动一步
                        #     position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                        #     continue
                        # else:
                        #     queue_charge.append(myFly[i]['no'])
                        RandomStep(MapInfo, map_grid, myFly[i], position, position_L, fromJ['UAV_enemy'],Fnum_value)  # 随机水平移动一步,无撞机    #出现了交叉撞机
                        position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                        continue
#分配到了目标机
                if goalGood[i] != 0 and 'goalP' in goalGood[i].keys():  # 分配到了敌机
                    # if myFly[i]['no'] in stack_atts:  # 分配到目标则删除战机身份
                    #     stack_atts.remove(myFly[i]['no'])
                    if myFly[i]['no'] in queue: # 分配到目标则删除待充电身份
                        queue.remove(myFly[i]['no'])
                    if goalGood[i]['no'] not in enemyno_positionN.keys():  # 撞我前已经挂了，则回复我机拉货状态
                        goalGood[i] = 0
                        closes_F[i].clear()
                        flag_up[i] = 1  # 上升
                        continue
                    if abs(myFly[i]['x'] - goalGood[i]['goalP'][0]) <= 1 and abs(myFly[i]['y'] - goalGood[i]['goalP'][1]) <= 1:  # 到达目标投放点上一步
                        if myFly[i]['z'] == h_low:
                            if abs(enemyno_positionN[goalGood[i]['no']][0] - goalGood[i]['goalP'][0]) <= 1 and abs(enemyno_positionN[goalGood[i]['no']][1] - goalGood[i]['goalP'][1]) <= 1 and \
                                            abs(enemyno_positionN[goalGood[i]['no']][2] - h_low) <= 1:
                                myFly[i]['x'] = goalGood[i]['goalP'][0]
                                myFly[i]['y'] = goalGood[i]['goalP'][1]
                                position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
                                continue
                            else:
                                continue
                        else:
                            if myFly[i]['z'] > h_low and [myFly[i]['x'], myFly[i]['y'],
                                                          myFly[i]['z'] - 1] in position:  # 下方有无人机，则不动
                                continue
                            myFly[i]['z'] -= 1
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
                            flag_up[i]=1 # 做好上升的准备
                            closes_F[i].clear()
                            continue
                    # if myFly[i]['x']==goalGood[i]['goalP'][0] and myFly[i]['y']==goalGood[i]['goalP'][1]:
                    #     if myFly[i]['z'] == h_low:
                    #         continue
                    #     else:
                    #         if myFly[i]['z'] > h_low and [myFly[i]['x'], myFly[i]['y'],myFly[i]['z'] - 1] in position:  # 下方有无人机，则不动
                    #             continue
                    #         myFly[i]['z'] -= 1
                    #         position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
                    #         flag_up[i]=1 # 做好上升的准备
                    #         closes_F[i].clear()
                    #         continue
                    else:
                        HoriAtt(MapInfo, map_grid, myFly[i], goalGood[i]['goalP'], closes_F[i], position, position_L, fromJ['UAV_enemy'], Fnum_value)
                        position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]
                        a = [myFly[i]['x'], myFly[i]['y']]
                        closes_F[i].append(a)
                        continue
#回坪前段水平移动
                if myFly[i]['no'] in queue and myFly[i]['z']==floor[myFly[i]['no']] :  #因为电量不够没分配到货物并且没分配到目标敌机则向充电桩水平移动  #有bug导致水平移动，必须保证在目标层执行
                    if max(abs(myFly[i]['x'] - mystart[0]), abs(myFly[i]['y'] - mystart[1])) > 4:  # 距离水平回坪点4步时加入队列
                        HoriAtt(MapInfo, map_grid, myFly[i], mystart, closes_F[i], position, position_L,fromJ['UAV_enemy'], Fnum_value)  # 向对方停机坪水平移动一步
                        a = [myFly[i]['x'], myFly[i]['y']]
                        closes_F[i].append(a)
                        position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                        continue
                    else:
                        if myFly[i]['no'] not in queue_charge:
                            queue_charge.append(myFly[i]['no'])
                        queue.remove(myFly[i]['no'])
                        continue

# 空载爬升过程
                if myFly[i]['goods_no'] == -1 and myFly[i]['z'] < floor[myFly[i]['no']] and flag_up[i] == 1:  # 空载上升
                    if myFly[i]['z'] >= (h_low - 1) and [myFly[i]['x'], myFly[i]['y'],myFly[i]['z'] + 1] in position:  # 上方有我方无人机，则不动
                        continue
                    else:
                        myFly[i]['z'] += 1
                        position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 记录当前无人机位置
                        a = [myFly[i]['x'], myFly[i]['y']]
                        closes_F[i].append(a)
                        continue

# 保证执行到此均已到达目标层且有目标货物  #并且目标均为货物# 空载水平飞行，有目标货物
                if myFly[i]['goods_no'] == -1 and myFly[i]['z'] == floor[myFly[i]['no']]:  # 到达目标层空载水平
                    if goalGood[i]['no'] in goods_nosta.keys() and goods_nosta[goalGood[i]['no']] == 0:  # 货物仍在,且可拉状态
                        if myFly[i]['x'] == goalGood[i]['start_x'] and myFly[i]['y'] == goalGood[i][
                            'start_y']:  # 当达目标上方下降一步
                            if myFly[i]['z'] > h_low and [myFly[i]['x'], myFly[i]['y'], myFly[i]['z'] - 1] in position:
                                continue
                            myFly[i]['z'] -= 1
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 记录当前无人机位置
                            flag_up[i] = 0  # 做好下降的准备
                            continue
                        else:
                            HoriFetch(MapInfo, map_grid, myFly[i], goalGood[i], closes_F[i], position, position_L,fromJ['UAV_enemy'], Fnum_value)  # 没到目标上方则水平移动
                            a = [myFly[i]['x'], myFly[i]['y']]
                            closes_F[i].append(a)  # 此处空载爬升转折点多记录了一次#刚好不多余
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 记录当前无人机位置
                            continue
                    else:
                        RandomStep(MapInfo, map_grid, myFly[i], position, position_L, fromJ['UAV_enemy'],Fnum_value)  # 随机水平移动一步,无撞机
                        position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 第i个无人机位置改变
                        goalGood[i] = 0
                        # closes_F[i].clear()
                        continue
# 空载下降，有目标货物
                if myFly[i]['goods_no'] == -1 and myFly[i]['z'] < floor[myFly[i]['no']] and flag_up[i] == 0:  # 空载下降,有目标货物状态
                    for no in fromJ['UAV_enemy']:  # 遍历当前对方无人机列表
                        if no['status'] == 1:
                            continue
                        if no['x'] == goalGood[i]['start_x'] and no['y'] == goalGood[i]['start_y'] and myFly[i]['z'] > no['z'] and Fnum_value[myFly[i]['type']] > Fnum_value[no['type']]:  # 在我的下方有对方机
                            myFly[i]['z'] += 1
                            goalGood[i] = 0
                            closes_F[i].clear()
                            flag_up[i] = 1
                            break
                    if flag_up[i] == 1:  # 说明下方有比我价值小的对方敌机
                        continue
                    # if myFly[i]['z'] == 0:  # 下降到地面，装货上升  #这不行，z=0才可改goods_no
                    #     myFly[i]['z'] += 1
                    #     myFly[i]['remain_electricity'] -= goalGood[i]['weight']  # 装货开始掉电
                    #     closes_F[i].clear()  # 清空closes_F
                    #     position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 记录当前无人机位置
                    #     continue
                    # else:
                    if myFly[i]['z'] > h_low and [myFly[i]['x'], myFly[i]['y'],myFly[i]['z'] - 1] in position:  # 下方有我方无人机，则不动
                        continue
                    myFly[i]['z'] -= 1  # 空载下降 goods_nosta
                    position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 记录当前无人机位置
                    if myFly[i]['z'] == 0:
                        if goalGood[i]['no'] in goods_nosta.keys() and goods_nosta[goalGood[i]['no']] == 0:  # 货物仍在
                            myFly[i]['goods_no'] = goalGood[i]['no']
                            goalGood[i]['status'] = 1  # 目标物被己方搭载
                            flag_up[i] = 1  # 空载货物可上升状态
                            myFly[i]['remain_electricity'] -= goalGood[i]['weight']  #装货开始掉电
                            closes_F[i].clear()
                            continue
                        else:  # 到达目的地后货物不在了，则返回从新开始
                            goalGood[i] = 0
                            closes_F[i].clear()  # 清空，重新从0开始升
                            flag_up[i] = 1  # 到达货物所在地后货物消失了，则上升
                            continue
# 负载上升
                if myFly[i]['goods_no'] != -1 and myFly[i]['z'] < floor[myFly[i]['no']] and steplen_P[i] <= floor[myFly[i]['no']]:  # 负载上升
                    if myFly[i]['z'] >= (h_low - 1) and [myFly[i]['x'], myFly[i]['y'], myFly[i]['z'] + 1] in position:  # 上方有我方无人机，则不动  #修改，等待也需要减电
                        myFly[i]['remain_electricity'] -= goalGood[i]['weight']
                        continue
                    myFly[i]['z'] += 1
                    myFly[i]['remain_electricity']-=goalGood[i]['weight']
                    position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 记录当前无人机位置
                    steplen_P[i] += 1  # 放置货物走过的步长统计
                    continue
# 负载水平飞行
                if myFly[i]['goods_no'] != -1 and myFly[i]['z'] == floor[myFly[i]['no']]:  # 载货，水平飞行，不判断是否有人蹲守
                    # 加入目标投放点是否有敌机蹲守判断
                    tempSafe = EnemyP(fromJ['UAV_enemy'], goalGood[i], myFly[i], Fnum_value, StaticEnes)  #更新静止敌机名单

                    if tempSafe == {} or abs(myFly[i]['x'] - goalGood[i]['end_x']) + abs(myFly[i]['y'] - goalGood[i]['end_y']) > 3 \
                            or myFly[i]['remain_electricity']<(myFly[i]['z']+7)*goalGood[i]['weight']:  # 无对方无人机蹲守 或者血量不够用了则冲下去
                        if myFly[i]['x'] == goalGood[i]['end_x'] and myFly[i]['y'] == goalGood[i]['end_y']:  # 当达目的地上方下降一步
                            if myFly[i]['z'] > h_low and [myFly[i]['x'], myFly[i]['y'],myFly[i]['z'] - 1] in position:  # 下方有我方无人机，则不动
                                myFly[i]['remain_electricity'] -= goalGood[i]['weight']
                                continue
                            myFly[i]['z'] -= 1
                            myFly[i]['remain_electricity'] -= goalGood[i]['weight']
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 记录当前无人机位置
                            steplen_P[i] += 1
                            continue
                        else:
                            a = [myFly[i]['x'], myFly[i]['y']]
                            closes_P[i].append(a)
                            HoriPut(MapInfo, map_grid, myFly[i], goalGood[i], closes_P[i], position, position_L,fromJ['UAV_enemy'], Fnum_value)  # 没到目标上方则水平移动   #此处closes_P[i]不好需要改进
                            # myFly[i]['x'],myFly[i]['y'] = goodspath[goalGood[i]['no']][floor[myFly[i]['no']]-h_low].pop(0)
                            myFly[i]['remain_electricity'] -= goalGood[i]['weight']
                            position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 记录当前无人机位置
                            steplen_P[i] += 1
                            continue
                    else:
                        # print('我是第%d个无人机，我的位置为：%d,%d,%d,有蹲守：'%(i,myFly[i]['x'],myFly[i]['y'],myFly[i]['z']))
                        # print(tempSafe)
                        myFly[i]['remain_electricity'] -= goalGood[i]['weight']
                        continue  # 有敌机蹲守则不动
# 负载下降
                if myFly[i]['goods_no'] != -1 and myFly[i]['z'] < floor[myFly[i]['no']] and steplen_P[i] > floor[
                    myFly[i]['no']]:  # 负载下降
                    if myFly[i]['z'] > h_low and [myFly[i]['x'], myFly[i]['y'],myFly[i]['z'] - 1] in position:  # 下方有我方无人机，则不动
                        myFly[i]['remain_electricity'] -= goalGood[i]['weight']
                        continue
                    myFly[i]['z'] -= 1  # 负载下降
                    myFly[i]['remain_electricity'] -= goalGood[i]['weight']
                    position[i] = [myFly[i]['x'], myFly[i]['y'], myFly[i]['z']]  # 记录当前无人机位置
                    if myFly[i]['z'] == 0:  # 到达目的地   下一次服务器返回goods_no为-1
                        closes_P[i].clear()  # 清空
                        steplen_P[i] = 0
                        goalGood[i] = 0  # 目标货物变为0，等待重新分配

        FlyPlane = copy.deepcopy(myFly)
        # print('我方无人机信息:')
        # for i in FlyPlane:
        #     print(i)
        temp = []
        for o in range(len(FlyPlane)):
            del FlyPlane[o]['type']
            if  FlyPlane[o]['status']!=1:#如果是撞毁的则不发
                del FlyPlane[o]['status']
                temp.append(FlyPlane[o])
        toJ['UAV_info'] = temp #格式参考fromJ
#购买无人机
        toJ['purchase_UAV'] = []  # 这里添加购买无人机请求
        total = sum(Ftype_num.values()) #我方存活的无人机数量
        totalenemy = len(enemyno_positionN)  # 对方无人机数量
        minvFnum=Ftype_num[UAV_price[0]['type']]  #最廉价的无人机数量
#测试
        if fromJ['we_value'] > 0 :#大于0则购买一个  全部价值用于购买
            # if total<=totalenemy:
            #     PurchaseNew(UAV_price, fromJ['we_value'],toJ['purchase_UAV']) #购买一个战机
            # else:
            toJ['purchase_UAV'] =Purchase(UAV_price,fromJ['we_value'], goodsLoad, fromJ, MapInfo, h_low,minvFnum)
        # print(toJ['purchase_UAV'])
        if toJ['purchase_UAV']==[]:  #如果没买到，则删除此键值对
            del toJ['purchase_UAV']

        nRet = SendJuderData1(hSocket, toJ)   #Player -> Judgerb  第一步发送0时刻位置 还没移动
        if nRet != 0:
            return nRet

        enemyno_goodsno={}
        enemyno_positionL ={}
        for e in range(len(fromJ['UAV_enemy'])):  #实时记录上一次对方无人机的编号和对应货物状态   #这种情况下，对方无人机坠毁后直接不返回，则enemyno_goodsno.keys()会多余一部分
            enemyno_goodsno[fromJ['UAV_enemy'][e]['no']] = fromJ['UAV_enemy'][e]['goods_no']
            enemyno_positionL[fromJ['UAV_enemy'][e]['no']]=[fromJ['UAV_enemy'][e]['x'],fromJ['UAV_enemy'][e]['y'],fromJ['UAV_enemy'][e]['z']] #记录上次对方无人机编号和对应位置
        toc = time.time()
        print('耗时:%d ms'%(1000*(toc-tic)))
        if fromJ["match_status"] == 1:
            print("game over, we value %d, enemy value %d\n"%(fromJ["we_value"], fromJ["enemy_value"]))
            hSocket.close()
            return 0

if __name__ == "__main__":
    if len(sys.argv) == 4:
        print("Server Host: " + sys.argv[1])
        print("Server Port: " + sys.argv[2])
        print("Auth Token: " + sys.argv[3])

        main(sys.argv[1], int(sys.argv[2]), sys.argv[3])

    else:
        print("need 3 arguments")