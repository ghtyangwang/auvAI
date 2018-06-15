#encoding=utf8
#author=高华涛
from game_functions import *
import random
import math
import Charge as ch


#停机坪通道单向复用，


#蹲守投放点上一位置水平移动
def HoriAtt(mapInfo, map_grid, myFly_dict,goal,closed_F,posit,position_L,enemyInfo,Fnum_value):
    # goal 三维点
    cur_p = [myFly_dict['x'], myFly_dict['y'], myFly_dict['z']]  # 此处原为二维点
    nextloc = NextPos_g(map_grid, mapInfo, closed_F, cur_p, goal,posit,position_L,enemyInfo,myFly_dict,Fnum_value)
    myFly_dict['x'] = nextloc[0]
    myFly_dict['y'] = nextloc[1]


#抓取货物追平移动
def HoriFetch(mapInfo, map_grid, myFly_dict, goalGood,closed_F,posit,position_L,enemyInfo,Fnum_value):
    goal =[goalGood['start_x'],goalGood['start_y']]
    cur_p =[myFly_dict['x'],myFly_dict['y'],myFly_dict['z']]  #此处原为二维点
    nextloc = NextPos_g(map_grid, mapInfo, closed_F, cur_p, goal,posit,position_L,enemyInfo,myFly_dict,Fnum_value)
    myFly_dict['x']=nextloc[0]
    myFly_dict['y']=nextloc[1]
#投放货物水平移动
def HoriPut(mapInfo, map_grid, myFly_dict, goalGood,closed_P,posit,position_L,enemyInfo,Fnum_value):
    goal = [goalGood['end_x'],goalGood['end_y']]
    cur_p = [myFly_dict['x'],myFly_dict['y'],myFly_dict['z']]  #此处原为二维点
    nextloc = NextPos_g(map_grid, mapInfo, closed_P, cur_p, goal,posit,position_L,enemyInfo,myFly_dict,Fnum_value)
    myFly_dict['x'] = nextloc[0]
    myFly_dict['y'] = nextloc[1]
    # myFly_dict['remain_electricity']-=goalGood['weight']
#随机水平移动
def RandomStep(mapInfo, map_grid,myFly_dict,position, position_L,enemyInfo,Fnum_value):  #水平随机走一步  #不合理，需要更改
    lis = []
    cur_p = [myFly_dict['x'], myFly_dict['y'], myFly_dict['z']]  # 此处原为二维点
    for i in range(-1, 2, 1):
        for q in range(-1, 2, 1):
            if q == 0 and i == 0:
                continue
            if myFly_dict['x']+i< 0 or myFly_dict['x']+i > mapInfo['map']['x'] - 1 or myFly_dict['y'] + q < 0 or myFly_dict['y'] + q > mapInfo['map']['x'] - 1:#地图出街要先判断
                continue
            if map_grid[myFly_dict['x'] + i, myFly_dict['y'] + q,  myFly_dict['z']] == 0:  # 建筑物
                continue
            exc = Diagonal(position, position_L, cur_p, i, q)
            excAtt = AttackPosit1(enemyInfo,myFly_dict,Fnum_value)   #此处表示随机漫步时可以撞对方等价值的无人机
            l = [myFly_dict['x'] + i, myFly_dict['y'] + q, myFly_dict['z']]
            if l in exc:
                continue
            if l in excAtt:
                continue
            if l in position:  #同一平面包括当前路径 有无人机
                continue
            lis.append(l)
            break
    if len(lis)>0:
        ind = random.randint(0,len(lis)-1)
        myFly_dict['x']=lis[ind][0]
        myFly_dict['y'] = lis[ind][1]

# #随机漫步，不重复
def RandomStepAtt(mapInfo, map_grid,myFly_dict,position, position_L,enemyInfo,Fnum_value,h_low,myFly,UAV_price):  #水平随机走一步  #不合理，需要更改
    lis = []
    cur_p = [myFly_dict['x'], myFly_dict['y'], myFly_dict['z']]  # 此处原为二维点
    for i in range(-1, 2, 1):
        for q in range(-1, 2, 1):
            if q == 0 and i == 0:
                continue
            if myFly_dict['x']+i< h_low or myFly_dict['x']+i > mapInfo['map']['x'] - h_low or myFly_dict['y'] + q < h_low or myFly_dict['y'] + q > mapInfo['map']['x'] - h_low:#地图出街要先判断
                continue
            if map_grid[myFly_dict['x'] + i, myFly_dict['y'] + q,  myFly_dict['z']] == 0:  # 建筑物
                continue
            exc = Diagonal(position, position_L, cur_p, i, q)
            excAtt = AttackPosit1(enemyInfo,myFly_dict,Fnum_value)   #此处表示随机漫步时可以撞对方等价值的无人机
            l = [myFly_dict['x'] + i, myFly_dict['y'] + q, myFly_dict['z']]
            if l in exc:
                continue
            if l in excAtt:
                continue
            if l in position:  #同一平面包括当前路径 有无人机
                continue
            # point = [myFly_dict['x']+i,myFly_dict['y'] + q]
            # neigh = ch.DisAtts(myFly,point, UAV_price,h_low)   #有问题，在范围内就都不动了，应为朝着远离方向移动
            # if neigh==True:
            #     continue
            lis.append(l)    #找到所有点
            # break
    mind = 0
    if len(lis)>0:
        for j in range(len(lis)):
            point = [lis[j][0],lis[j][1]]
            d, neigh = ch.DisAtts(myFly,point,UAV_price,h_low)
            if neigh==False:
                myFly_dict['x']=lis[j][0]
                myFly_dict['y'] = lis[j][1]
                break
            elif d >mind:
                mind=d
                myFly_dict['x'] = lis[j][0]
                myFly_dict['y'] = lis[j][1]










