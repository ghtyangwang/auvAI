#encoding=utf8
#author=高华涛
import json
import socket
import time
import numpy as np
import copy
import math
import Charge as ch
# 定义一个含有障碍物的栅格地图
# 10表示可通行点
# 0表示障碍物
# 1表示雾区
#构建三维栅格地图
def MapBuild(x, y, z, building_list, parking_dict, fog_list): #加入fog雾区
    map_grid = np.full((x,y,z),10)
    build_num = len(building_list)
    fog_num = len(fog_list)
    for q in range(fog_num):
        fxs = fog_list[q]['x'];fxe = fog_list[q]['x']+fog_list[q]['l']
        fys = fog_list[q]['y'];fye = fog_list[q]['y']+fog_list[q]['w']
        fzs = fog_list[q]['b'];fze = fog_list[q]['t']+1
        map_grid[fxs:fxe,fys:fye,fzs:fze]=1
    for i in range(build_num):
        xs = building_list[i]['x']
        xe = building_list[i]['x']+building_list[i]['l']
        ys = building_list[i]['y']
        ye = building_list[i]['y']+building_list[i]['w']
        h = building_list[i]['h']
        map_grid[xs:xe, ys:ye,0:h]=0  #障碍物
    return map_grid

def my_no(t):  #t为列表中的元素
    return t['no']
def my_dist(t):   #按照到原点距离从小到大排序
    dist = t['start_x']+t['start_y']
    return dist
def my_weight(t):
    return t['weight']
def goods_value(t):#按照value从大到小排列   #改为按照value/起始距离
    # pow_dis = pow(t['start_x']-t['end_x'],2)+pow(t['start_y']-t['end_y'],2)
    # dis = math.sqrt(pow_dis)//1
    dis = ch.distance(t['start_x'],t['start_y'],t['end_x'],t['end_y'])
    if dis==0:
        return t['value']
    return t['value']/dis
#返回输入的无人机要去搭载的货物字典
#可靠略购买L/V最大的无人机
def MaxLoad(fromJ, uav_info_dict, goalGood_list, Fnum_lw,floor,goodspath,h_low,goodsAtt):   #捡货物是按照最大可载货物优先  #电量够用
    goods_list = sorted(fromJ['goods'], key=goods_value,reverse=True)  # id不同,对货物按照value从大到小排序
    goods_num = len(goods_list)
    myload = {}
    goalgood_no = []  #提取已加入我方目标列表的货物编号   #注意：此处应该去除被战机锁定的货物编号
    cnt = 0 #统计是否应该加入queue_charge
    for j in range(len(goalGood_list)):
        if goalGood_list[j]==0 or 'goalP' in goalGood_list[j].keys():
            continue
        if goalGood_list[j]['no'] in goodsAtt:
            continue
        goalgood_no.append(goalGood_list[j]['no'])  #被排除的货物名单,不包括战机目标
    for i in range(goods_num):    #遍历所有goods,寻找价值最大的物品
        if goods_list[i]['status']==1:   #已被捡起
            continue
        if goods_list[i]['no'] in goalgood_no:  #此货物编号已被我方其他无人机占用
            continue
        time_terminal = abs(uav_info_dict['z']-floor[uav_info_dict['no']])+floor[uav_info_dict['no']]\
                        +ch.distance(uav_info_dict['x'],uav_info_dict['y'],goods_list[i]['start_x'],goods_list[i]['start_y'])
        if time_terminal > goods_list[i]['left_time']:
            continue
        if time_terminal+fromJ['time']<=goods_list[i]['start_time']:  #这个冗余，不可能出现，不可能出现未来才出现的物品，只有0 1 态
            continue
        tp = uav_info_dict['type']  # F1
        if Fnum_lw[tp] < goods_list[i]['weight']:  # 载不动的货物过滤掉
            continue
        myf = floor[uav_info_dict['no']]-h_low
        path = goodspath[goods_list[i]['no']][myf]
        time_put = len(path) +2*floor[uav_info_dict['no']]   #比正确计算多1+3  留有余量
        if uav_info_dict['remain_electricity']>time_put*goods_list[i]['weight']:  #电量够用   #此处有bug  应为找到目标货物即break
            myload = goods_list[i]
            break
        else:
            cnt+=1
    return myload,cnt   #目标货物的字典记录

#根据UAV_price返回type:value   传入l为UAV_price列表
def TypeValue(l):
    type_value = {}
    for i in range(len(l)):
        type_value[l[i]['type']]=l[i]['value']
    return type_value #{'F1':300,F2':200,...}
#根据UAV_price返回type:load_weight
def TypeLoad(l):
    type_load = {}
    for i in range(len(l)):
        type_load[l[i]['type']]=l[i]['load_weight']
    return type_load #{'F1':100,'F2':50...}
#根据UAV_price返回type:capacity, type:charge
def TypeCapacityCharge(l):
    type_capacity ={}
    type_charge = {}
    for i in range(len(l)):
        type_capacity[l[i]['type']]=l[i]['capacity']
        type_charge[l[i]['type']]=l[i]['charge']
    return type_capacity, type_charge



#单架无人机开始规划 cur_p当前点列表
def h_value(cur_p, goal):
    # h = abs(cur_p[0]-goal[0])+abs(cur_p[1]-goal[1])
    h=(math.sqrt(2)-1)*min(abs(cur_p[0]-goal[0]),abs(cur_p[1]-goal[1]))+max(abs(cur_p[0]-goal[0]),abs(cur_p[1]-goal[1]))
    return h
def NextPos_g(map_grid, MapInfo, closed_l, cur_p, goal, posit,position_L, enemyInfo,myFly_dict,Fnum_value):  #等高度判断  position  position_L   #enemyInfo同UAV_enemy
    open_list = []
    open_f = []
    exc = []
    for j in range(-1,2,1):
        for q in range(-1,2,1):
            if j==0 and q==0:
                continue
            if cur_p[0]+j<0 or cur_p[0]+j>MapInfo['map']['x']-1 or cur_p[1]+q<0 or cur_p[1]+q>MapInfo['map']['y']-1:#地图出界了，二维出界
                continue
            if [cur_p[0]+j,cur_p[1]+q,cur_p[2]] in posit:#下一个点为己方无人机位置
                continue
            if map_grid[cur_p[0] + j, cur_p[1] + q, cur_p[2]] == 0:  # 建筑物   #此处不可以用0，否则在建筑物上方飞行都不可以
                continue
            if [cur_p[0]+j,cur_p[1]+q] in closed_l:  #不是上一个点，防止两点间来回  包含水平移动的所有走过的二维点坐标
                continue
            exc = Diagonal(posit,position_L, cur_p, j,q)  #exc中包含构成对角线路径的下一个点，无则返回[]  #测试无差错，可以避开与已移动的无人机构成对角线交叉
            excAtt = AttackPosit(enemyInfo,myFly_dict,Fnum_value)
            if [cur_p[0]+j,cur_p[1]+q,cur_p[2]] in exc:
                continue
            if [cur_p[0]+j,cur_p[1]+q,cur_p[2]] in excAtt:
                continue
            if [cur_p[0]+j,cur_p[1]+q,cur_p[2]] in posit:#此处新增，若有我方无人机则排除
                continue
            open_list.append([cur_p[0]+j,cur_p[1]+q])
            f_tmp = h_value([cur_p[0]+j,cur_p[1]+q], goal)
            open_f.append(f_tmp)
    if len(open_f)==0:  #如果没有合适下一个点，原地不动
        location = [cur_p[0],cur_p[1]]
        return location
    index = open_f.index(min(open_f))#F值最小索引
    location = open_list[index] #下一个当前点
    return location

def GoodStatus(fromJ):#根据fromJ返回货物编号和货物状态字典
    result_dict = {}
    no_lefttime={}
    goodslist = copy.deepcopy(fromJ['goods'])
    for i in range(len(goodslist)):
        if goodslist[i]['left_time']==0:#此种状态不可被搭载，同消失删除
            continue
        result_dict[goodslist[i]['no']] = goodslist[i]['status']
        no_lefttime[goodslist[i]['no']] = goodslist[i]['left_time']
    return result_dict,no_lefttime
#产生对角线交叉禁走点
def Diagonal(posit, position_L, cur_p, j, q):
    exclu = []
    for i in range(len(posit)):  # position_L  posit
        if posit[i]==None:#表示该无人机为坠毁状态
            continue
        if cur_p == posit[i]:  # 自己点
            continue
        if cur_p[2] != posit[i][2]:  # 不在同一高度
            continue
        dx0 = (cur_p[0] - position_L[i][0])
        dx1 = (cur_p[0] + j - posit[i][0])
        dy0 = (cur_p[1] - position_L[i][1])
        dy1 = (cur_p[1] + q - posit[i][1])
        if dy1 == 0 and dy0 == 0 and dx0 * dx1 == -1:  # 此点即为对角点需抛出
            # print('对角点检测1，与第%d个无人机路径构成对角,：'%(i))
            # print(position_L[i])
            # print(posit[i])
            # print(cur_p)
            # print([cur_p[0] + j, cur_p[1] + q, cur_p[2]])
            exclu.append([cur_p[0] + j, cur_p[1] + q, cur_p[2]])
        if dy0 * dy1 == -1 and dx0 == 0 and dx1 == 0:
            # print('对角点检测2,与第%d个无人机路径构成对角,：'%(i))
            # print(position_L[i])
            # print(posit[i])
            # print(cur_p)
            # print([cur_p[0] + j, cur_p[1] + q, cur_p[2]])
            exclu.append([cur_p[0] + j, cur_p[1] + q, cur_p[2]])
    return exclu  # 水平移动时，需要被排除在外的点

#产生下一步可能跟比较大的无人机撞的可能点
def AttackPosit(enemyInfo,myfly_dict,Fnum_value):#返回无人机需要规避的对方点，同一高度水平方向
    result_list = []
    for i in range(len(enemyInfo)):
        if Fnum_value[enemyInfo[i]['type']]<=Fnum_value[myfly_dict['type']] and enemyInfo[i]['z']==myfly_dict['z']:#需要规避的无人机,躲开价值比我小和相等的
        # if enemyInfo[i]['z']==myfly_dict['z']:
            for j in range(-1, 2, 1):
                for q in range(-1, 2, 1):
                    if j == 0 and q == 0:
                        continue
                    result_list.append([enemyInfo[i]['x']+j, enemyInfo[i]['y']+q,enemyInfo[i]['z']])
    return result_list  #包含了下一步移动需要排除的点

def AttackPosit1(enemyInfo,myfly_dict,Fnum_value):#返回无人机需要规避的对方点，同一高度水平方向
    result_list = []
    for i in range(len(enemyInfo)):
        if Fnum_value[enemyInfo[i]['type']]<Fnum_value[myfly_dict['type']] and enemyInfo[i]['z']==myfly_dict['z']:#需要规避的无人机,躲开价值比我小和相等的
        # if enemyInfo[i]['z']==myfly_dict['z']:
            for j in range(-1, 2, 1):
                for q in range(-1, 2, 1):
                    if j == 0 and q == 0:
                        continue
                    result_list.append([enemyInfo[i]['x']+j, enemyInfo[i]['y']+q,enemyInfo[i]['z']])
    return result_list  #包含了下一步移动需要排除的点



#选择的货物保证其可以分配到货物,先从最小的开始购买  #改为：批量购买
def Purchase(UAV_price, value, goodsLoad, fromJ,mapInfo, h_low,minvFnum):#
    purc_list = []
    goods_list = sorted(fromJ['goods'],key=my_weight) #按照货物重量从小到大
    cost = 0   #本次购买消费的钱数
    excgoods = copy.deepcopy(goodsLoad)  #存放已被我方锁定目标货物编号
    ind =0
    time = 0
    while ind <len(UAV_price):    #考虑是否 购买第ind货物  按照货物分布购买
        time = UAV_price[ind]['capacity']/UAV_price[ind]['charge']#第ind种无人机充电时间
        flag = 0  #标志该种无人机是否找到目标物
        for q in range(len(goods_list)):
            if goods_list[q]['no'] in excgoods:#货物已被预订
                continue
            if goods_list[q]['status']==1:
                continue
            if goods_list[q]['weight']>UAV_price[ind]['load_weight']:
                break
            dist = 2*h_low + ch.distance(mapInfo['parking']['x'],mapInfo['parking']['y'],goods_list[q]['start_x'],goods_list[q]['start_y'])+time
            if dist < goods_list[q]['left_time']:
                if cost+UAV_price[ind]['value']<=value:
                    purc_list.append({'purchase':UAV_price[ind]['type']})
                    cost+=UAV_price[ind]['value']
                    excgoods.append(goods_list[q]['no'])
                    flag=1
                    break
                else:  #钱不够则退出
                    flag=2
                    break
        if flag==0:  #此种无人机没找到货物，下次从下一种开始
            ind+=1
        if flag==2:
            break
    minvF=0
    if value-cost>UAV_price[0]['value']:
        minvF= (value-cost)//UAV_price[0]['value']  #还可购买的最廉价机的数量
    if minvFnum<3 and minvF>0:
        for i in range(minvF):
            purc_list.append({'purchase': UAV_price[0]['type']})
    return purc_list  #发送的格式

#如果我方无人机数量少于对方则批量购买最便宜的
def PurchaseNew(UAV_price, value,purchase_UAV):
    num = value//UAV_price[0]['value']
    for i in range(num):
        purchase_UAV.append({'purchase': UAV_price[0]['type']})
    # while total<=totalenemy:
    #     if value>=UAV_price[0]['value']:  #买得起最便宜的无人机
    #         purchase_UAV.append({'purchase':UAV_price[0]['type']})
    #         total+=1
    #         value-=UAV_price[0]['value']
    #     else:
    #         break
    # if value>=UAV_price[0]['value']:  #一次购买一个战机
    #     purchase_UAV.append({'purchase': UAV_price[0]['type']})



#返回目标敌机，和目标投放点位置
#策略：用最便宜的无人机作为攻击机，单独处理，如最便宜的无人机为F4
#Ftype_value攻击机，UAV_price中最便宜的，数量根据对方无人机数量来定  enemyFly=[{},{}]
def AttackTarget(UAV_enemy, Ftype_value, myAtt_dict,low_h, gNo_pos,enemyno_goodsno,goalGood,stack_F3):   #goal_list中存放goalGood中的目标货物编号或目标位置
    goalFly=0
    goal_list=[]  #排除列表
    for j in goalGood:
        if j==0:
            continue
        if 'goalP' in j.keys():   #木白哦蹲守敌机的货物投放点
            goal_list.append(j['goalP'])
    for i in range(len(UAV_enemy)):   #寻找有货物运输的
        if UAV_enemy[i]['no'] in stack_F3:  #该敌机已被追踪
            continue
        if UAV_enemy[i]['status']!=0:#敌机坠毁或雾区中，不考虑
            continue
        if UAV_enemy[i]['no'] not in enemyno_goodsno.keys():#对方刚买的，不考虑
            continue
        if UAV_enemy[i]['goods_no']!=-1:#已经搭载上货物
            if [gNo_pos[UAV_enemy[i]['goods_no']][0],gNo_pos[UAV_enemy[i]['goods_no']][1]] in goal_list:#目标敌机已被我方其他无人机占用
                continue
            # dx = UAV_enemy[i]['x']-gNo_pos[UAV_enemy[i]['goods_no']][0]
            # dy = UAV_enemy[i]['y']-gNo_pos[UAV_enemy[i]['goods_no']][1]
            # distene =abs(dx)+abs(dy)+UAV_enemy[i]['z']+low_h #敌机从取得货物到达到投放点最低飞行高度的最少步长
            distene = ch.distance(UAV_enemy[i]['x'],UAV_enemy[i]['y'],gNo_pos[UAV_enemy[i]['goods_no']][0],gNo_pos[UAV_enemy[i]['goods_no']][1])+low_h+UAV_enemy[i]['z']
            mytime = ch.distance(myAtt_dict['x'],myAtt_dict['y'],gNo_pos[UAV_enemy[i]['goods_no']][0],gNo_pos[UAV_enemy[i]['goods_no']][1])+myAtt_dict['z']-low_h
            # mytime = abs(myAtt_dict['x']-gNo_pos[UAV_enemy[i]['goods_no']][0])+abs(myAtt_dict['y']-gNo_pos[UAV_enemy[i]['goods_no']][1])+myAtt_dict['z']-low_h#到达该敌机上空最低投放位置的最大时间
            if mytime<=distene  and Ftype_value[UAV_enemy[i]['type']]>=Ftype_value[myAtt_dict['type']]:   #找到满足条件的比我贵或者相等的敌机
                goalFly = copy.deepcopy(UAV_enemy[i])
                goalP = [gNo_pos[UAV_enemy[i]['goods_no']][0],gNo_pos[UAV_enemy[i]['goods_no']][1]]
                goalFly['goalP']=goalP
                break
    return goalFly  #myAtt_dict攻击目标敌机
#跟踪目标机
def AttackTargetF3(UAVene_sort,myFly_dict,h_low,stack_F3,Fnum_value):
    '''
    :param UAVene_sort: 对方敌机按照value从大到小
    :param Fnum_value:无人机类型和价格表
    :param myFly_dict:
    :param enemyno_goodsno:
    :param gNo_pos:
    :return:
    '''
    goalFly =0
    for i in range(len(UAVene_sort)):
        if Fnum_value[myFly_dict['type']]>=Fnum_value[UAVene_sort[i]['type']]:#价值小于等于我方战机直接跳出
            break
        if UAVene_sort[i]['status']==2:#雾区
            continue
        if UAVene_sort[i]['no'] in stack_F3: #已被战机锁定
            continue
        # if UAVene_sort[i]['no'] in enemymenu: #已被蹲守
        #     continue
        # if UAVene_sort[i]['remain_electricity']<=10: #表示没充电
        #     continue
        d = ch.distance(myFly_dict['x'],myFly_dict['y'],UAVene_sort[i]['x'],UAVene_sort[i]['y'])  #返回起点到终点的步数
        if d<4*h_low:
            goalFly = copy.deepcopy(UAVene_sort[i]) #追踪的目标机
            break
    return goalFly



#增加返回是以货物数量和平均值的功能
def Goods_NoPosit(goods_l,h_low):
    '''
    :param goods_l: fromJ['goods']
    :return: 货物的编号和目标位置列表的字典
    '''
    no_goalposit ={}
    # Counts = 0  # 适宜的货物数量
    for i in range(len(goods_l)):
        no_goalposit[goods_l[i]['no']] = [goods_l[i]['end_x'],goods_l[i]['end_y']]
        # if goods_l[i]['status']==1:
        #     continue
        # if goods_l[i]['left_time']<2*h_low:
        #     continue
        # Ave+=goods_l[i]['weight']
        # Counts+=1
    # if Counts==0:
    #     return no_goalposit
    # else:
    return no_goalposit


def EnemyApron(UAV_enemy):
    apron = []
    if UAV_enemy[0]['x']==-1 and UAV_enemy[0]['y']==-1 and UAV_enemy[0]['z']==-1:#表示对方停机坪在雾区中，此时停机坪蹲守计划不执行
        return apron
    else:
        apron.append(UAV_enemy[0]['x'])
        apron.append(UAV_enemy[0]['y'])
        # apron.append(UAV_enemy[0]['z'])
        return apron   #如果不在雾区中返回对方停机坪三维点位置


#获取最廉价的无人机字典
def MinCostFly(mapInfo):
    lowcost = {}
    tmp = float('inf')
    for i in range(len(mapInfo['UAV_price'])):
        if mapInfo['UAV_price'][i]['value']<tmp:
            tmp = mapInfo['UAV_price'][i]['value']
            lowcost = mapInfo['UAV_price'][i]
    return lowcost

#判断是否有无人机蹲守
def EnemyP(UAV_enemy,mygoalGood, myFly_dict, Fnum_value,StaticEnes):#对方无人机列表
    p={}
    for ie in range(len(UAV_enemy)):
        if UAV_enemy[ie]['x']==mygoalGood['end_x'] and UAV_enemy[ie]['y']==mygoalGood['end_y'] and \
                        UAV_enemy[ie]['z']<=myFly_dict['z'] and Fnum_value[UAV_enemy[ie]['type']]<=Fnum_value[myFly_dict['type']] :
            p[UAV_enemy[ie]['no']]= [UAV_enemy[ie]['x'],UAV_enemy[ie]['y'],UAV_enemy[ie]['z']]
            # if UAV_enemy[ie]['no'] not in StaticEnes.keys():
            StaticEnes[UAV_enemy[ie]['no']] = [UAV_enemy[ie]['x'],UAV_enemy[ie]['y'],UAV_enemy[ie]['z']]  #StaticEnes实时添加和位置更新
            break

    return p  #为{}表示无对方敌机蹲守  否则返回对方敌机的编号:三维点列表
'''以下为改善主题循环结构部分，考虑电量问题'''
def No_positN(UAV_enemy):
    '''记录当前对方无人机编号和对应位置'''
    enemy_pN={}
    for i in UAV_enemy:
        if i['status']==1:
            continue
        enemy_pN[i['no']] = [i['x'],i['y'],i['z']]
    return enemy_pN

def myFlyUpdate(UAV_me,myFly,goalGood,position,position_L,closes_F,closes_P,Ftype_num,steplen_P,floor,flag_up,high_low,h_low,queue_charge,stack_atts):
    '''更新Ftype_num字典，判断是否坠毁'''
    UAV_me_list =sorted(UAV_me, key=my_no)  #按照'no'从小到大进行排序
    for i in range(len(UAV_me_list)):
        if UAV_me_list[i]['status']==1 and myFly[UAV_me_list[i]['no']]['status']!=1:
            myFly[UAV_me_list[i]['no']]['status']=1
            goalGood[UAV_me_list[i]['no']]=0
            position[UAV_me_list[i]['no']]=None
            position_L[UAV_me_list[i]['no']]=None
            closes_F[UAV_me_list[i]['no']].clear()
            closes_P[UAV_me_list[i]['no']].clear()
            Ftype_num[UAV_me_list[i]['type']]-=1
            if myFly[UAV_me_list[i]['no']]['no'] in queue_charge:  #追毁则从待充电队列中删除
                queue_charge.remove(myFly[UAV_me_list[i]['no']]['no'])
            if myFly[UAV_me_list[i]['no']]['no'] in stack_atts:    #坠毁则从战机堆栈中删除，并清空位置
                stack_atts.remove(myFly[UAV_me_list[i]['no']]['no'])

        if UAV_me_list[i]['no']>=len(myFly):   #需要更改
            if 'load_weight' in UAV_me_list[i].keys():
                del UAV_me_list[i]['load_weight']
            myFly.append(UAV_me_list[i])  # 和myFly绑定的变量同步更新
            goalGood.append(0)
            closes_F.append([])
            closes_P.append([])
            steplen_P.append(0)  # 初始走过的步长
            # position.append([UAV_me_list[i]['x'], UAV_me_list[i]['y'], UAV_me_list[i]['z']])
            position.append(None)  #初始位置为0
            position_L.append([UAV_me_list[i]['x'], UAV_me_list[i]['y'], UAV_me_list[i]['z']])
            floor[UAV_me_list[i]['no']] = UAV_me_list[i]['no'] % (high_low) + h_low  # {0:7,1:8,2:9,3:7} 初始化无人机数据，后面需要更新  #此处层数可更改
            flag_up.append(1)  # 新购买的无人机上升
            if UAV_me_list[i]['type'] in Ftype_num.keys():  # 若果已存在则加一个，否则赋值为1，myFly中无人机
                Ftype_num[UAV_me_list[i]['type']] += 1
            else:
                Ftype_num[UAV_me_list[i]['type']] = 1
        position_L[UAV_me_list[i]['no']] = [UAV_me_list[i]['x'], UAV_me_list[i]['y'],
                                            UAV_me_list[i]['z']]  # 'no'号我方无人机移动前位置记录
        if UAV_me_list[i]['goods_no'] == -1:  # 表示已送达的情况
            myFly[UAV_me_list[i]['no']]['goods_no'] = -1


def enemyUpdate(stack_F3,enemyno_positionN):
    li = []
    for i in range(len(stack_F3)):
        if stack_F3[i] not in enemyno_positionN.keys():
            li.append(stack_F3[i])
    for i in li:
        stack_F3.remove(i)





