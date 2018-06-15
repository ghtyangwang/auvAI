#encoding=utf8
#author=高华涛
import math
import numpy as np
import copy

#充一次电过程
def charge(myFly_dict, Fnum_capacity, Fnum_charge):
    if myFly_dict['remain_electricity']<Fnum_capacity[myFly_dict['type']]:#没充满
        myFly_dict['remain_electricity'] += Fnum_charge[myFly_dict['type']]
    if myFly_dict['remain_electricity']>Fnum_capacity[myFly_dict['type']]:#已经充满
        myFly_dict['remain_electricity'] = Fnum_capacity[myFly_dict['type']]

#调用此函数前提是没有无人机回坪并且充满了   分组管理：充电、拉货
def OutArra(myFly_dict, position):
    '''无人机出坪调度'''
    next= [myFly_dict['x'],myFly_dict['y'],myFly_dict['z']+1]
    if next in position:#前面有无人机了
        return
    else:
        myFly_dict['z']+=1

def InArra(myFly_dict, position):
    '''无人机回坪调度算法'''
    if myFly_dict['z'] - 1==0:#下一步我停机坪则直接进入
        myFly_dict['z'] -= 1
        return
    next = [myFly_dict['x'], myFly_dict['y'], myFly_dict['z'] - 1]
    if next in position:  # 前面有无人机了
        return
    else:
        myFly_dict['z'] -= 1

# def NumCharge(myFly,mystart):
#     '''统计充电无人机数量'''
#     cnt = 0
#     for i in range(len(myFly)):
#         if myFly[i]['status']==3:
#             cnt+=1
#             continue
#         # if [myFly[i]['x'],myFly[i]['y']]==mystart:

def BFS(map_grid, high, start, goal):
    '''
    :param map_grid: 三维数组地图
    :param high:飞行的层数
    :param start: 二维元组
    :param goal: 二维元组
    :return:最短路径步数和对应从起点到终点的list
    '''
    map2 = map_grid[:,:,high]  #取飞行高度high上的二维数组
    print('高度为：%d对应二维地图信息：'%high)
    print(map2)
    result=[]
    xarr = map2.shape[0];yarr = map2.shape[1]
    dist=[]  #每个元素记录对应格子到起点的距离，初始为1000无穷大
    path=[]  #每个元素记录对应格子的父节点的位置坐标元组,初始为0
    for i in range(xarr):
        dist.append([])
        path.append([])
        for j in range(yarr):
            dist[i].append(1000)   #最大距离定义为1000，即为无穷大，每个点只访问一次
            path[i].append(0)
    queue = []
    queue.append(start)
    dist[start[0]][start[1]] = 0
    path[start[0]][start[1]] = start
    while queue!=[]:
        posit = queue.pop(0)
        if posit == goal:
            break
        for i in range(-1,2,1):
            for q in range(-1,2,1):
                if i==0 and q==0:
                    continue
                if posit[0]+i>=0 and posit[0]+i<xarr \
                    and posit[1]+q>=0 and posit[1]+q<yarr \
                    and map2[posit[0]+i][posit[1]+q]!=0 \
                    and dist[posit[0]+i][posit[1]+q]==1000:  #可访问并且只访问一次
                    queue.append((posit[0]+i,posit[1]+q)) #可访问点坐标
                    dist[posit[0]+i][posit[1]+q]=dist[posit[0]][posit[1]]+1
                    path[posit[0]+i][posit[1]+q] = (posit[0],posit[1])
    steps = dist[goal[0]][goal[1]]  #最短距离
    p_list = []
    p=goal
    p_list.append(goal)
    for i in range(steps-1):  #排除起点坐标
        p_list.append(path[p[0]][p[1]])
        p=path[p[0]][p[1]]
    result = p_list[::-1]  #倒序，如此输出的位从从起点到终点，两点均在内
    return result

#返回字典，键为货物唯一编号，值为从起点到终点二维平面的列表  行数为货物数，列数为层数，最高三层
def GoodsPath(map_grid,goods,high_low,h_low, goodspath, gNo_position):   #{'no':[[],[],[]]}
    del_list = []
    for k in goodspath.keys():  #字典在遍历时不能修改
        if k not in gNo_position.keys(): #此货物编号已不再货物列表中,从goodspath删除键值对
            del_list.append(k)
    for j in range(len(del_list)):
        del goodspath[del_list[j]]
    for i in range(len(goods)):  #针对每个货物进行规划
        if goods[i]['status']==1:#已被捡起不考虑
            continue
        if goods[i]['no'] in goodspath.keys(): #已被规划过了
            continue
        goodspath[goods[i]['no']] = []
        start = (goods[i]['start_x'],goods[i]['start_y'])
        end = (goods[i]['end_x'],goods[i]['end_y'])
        for q in range(high_low):  #每层的不同规划
            #path_l = BFS(map_grid,q+h_low,start,end)
            path_l = cal_distance(map_grid,q+h_low,start,end)
            goodspath[goods[i]['no']].append(path_l)

def distance(start_x,start_y,end_x,end_y):
    return (math.sqrt(2)-1)*min(abs(start_x-end_x),abs(start_y-end_y))+max(abs(start_x-end_x),abs(start_y-end_y))
    # return max(abs(start_x-end_x),abs(start_y-end_y))


def cal_distance(map_grid,h,start,end):
    openlist=[]
    closelist=[]
    start_x = start[0]
    start_y = start[1]
    end_x = end[0]
    end_y = end[1]
    start_pt=(start_x,start_y)
    end_pt=(end_x,end_y)

    obstaclelist=[]
    temp_pt = start_pt
    closelist.append(temp_pt)
    while temp_pt != end_pt:
        min_pt=0
        min_dis=float("inf")
        for i in range(-1,2,1):
            for j in range(-1,2,1):
                pt=(temp_pt[0]+i,temp_pt[1]+j)
                if pt[0]<0 or pt[0]>=map_grid.shape[0]:
                    continue
                if pt[1]<0 or pt[1]>=map_grid.shape[1]:
                    continue
                if pt in closelist or map_grid[pt[0],pt[1],h]==0:
                    continue
                dis=distance(pt[0],pt[1],end_x,end_y)
                if dis <min_dis:
                    min_dis=dis
                    min_pt=pt

        temp_pt=min_pt
        closelist.append(temp_pt)
    # print(len(closelist)) # 距离
    # print(closelist)
    return closelist

def ApronFlys(myFly,Fnum_capacity, mystart,h_high,UAV_price):
    '''统计我方在无人机通道上出坪的数量'''
    numap = 0 #无人机通道上我方无人机数量
    for i in range(len(myFly)):
        if myFly[i]['status']==1:#坠毁不考虑
            continue
        if Fnum_capacity[myFly[i]['type']]>myFly[i]['remain_electricity'] and myFly[i]['type']!=UAV_price[0]['type']:  #表示非满电
            continue
        if [myFly[i]['x'],myFly[i]['y']] == mystart and myFly[i]['z']>=1 and myFly[i]['z']<=h_high:#在我方停机坪通道上
            numap+=1
    return numap
def EnyApronCNT(UAV_enemy,enemy_apron):
    '''对方在停机坪中的数量'''
    cnt =0
    for i in range(len(UAV_enemy)):
        if [UAV_enemy[i]['x'],UAV_enemy[i]['y']]==enemy_apron and UAV_enemy[i]['z']==0: #对方无人机在停机坪中
            cnt+=1
    return cnt  #对方载停机坪中的数量

def DisApronEne(myFly_dict, enemy_apron):  #返回距离对方停机坪位置的水平
    dis = abs(myFly_dict['x']-enemy_apron[0]) +abs(myFly_dict['y']-enemy_apron[1])
    return dis

#均匀分割地图，布置无目标的战机，按区域分
# def LayoutAtt(mapInfo, map_grid,goods,h_low):
#     centr = [mapInfo['map']['x']//2,mapInfo['map']['y']//2]  #地图中心点
def DisAtts(myFly,point,UAV_price,h_low): #判断其周围h_low距离内是否有我方无人机,point为二维点
    resul =0  #无穷大
    neigh = False
    for i in myFly:
        if i['status']==1:
            continue
        if i['type'] !=UAV_price[0]['type']:
            continue
        d = distance(point[0],point[1],i['x'],i['y'])
        if d<2*h_low :
            resul = d   #找出范围内的距离
            neigh = True
    return resul,neigh   #该点周围存在战机则返回True




def Confirm(goalGood,myFly,UAV_price):
    enemenu = []  #存防被我方敌机锁定的敌机'no'
    goods =[]
    goodsAtt=[]
    for i in range(len(myFly)):
        if goalGood[i]==0:
            continue
        if 'weight' in goalGood[i].keys():  #表示目标为货物
            if myFly[i]['type'] ==UAV_price[0]['type'] and myFly[i]['remain_electricity']==0:#战机,被战机锁定的货物
                goodsAtt.append(goalGood[i]['no'])
            else:
                goods.append(goalGood[i]['no'])
        if 'type' in goalGood[i].keys():
            enemenu.append(goalGood[i]['no'])
    return enemenu,goodsAtt,goods

def valuesort(t):
    return t['value']
def MaxLoadAtt(goodsLoad,goodsAtt,fromJ):
    goods_list = sorted(fromJ['goods'], key=valuesort, reverse=True)  # id不同,对货物按照value从大到小排序
    mygoal=0
    for i in range(len(goods_list)):
        if goods_list[i]['status']==1:
            continue
        if goods_list[i]['no'] in goodsLoad or goods_list[i]['no'] in goodsAtt:#被我货机或战机定位
            continue
        mygoal = goods_list[i]
        break
    return mygoal

def StaticAtt(StaticEnes,myFly_dict, UAV_enemy,stack_F3,h_low):   #分配目标静止机
    goalFly = 0
    no=-1
    mind = float("inf")
    for k,v in StaticEnes.items():
        if k in stack_F3:  #已被追踪
            continue
        d = distance(myFly_dict['x'],myFly_dict['y'],v[0],v[1])+abs(v[2]-h_low)  #到达给点所需要的时间
        if d<mind:
            mind=d
            # goalFly = {k:v}
            no = k
    if no!=-1:#分配成功  no！=-1
        for i in UAV_enemy:
            if i['no']==no:
                goalFly=i
                break
    return goalFly    #寻找出一个最近的静止敌机

def StaticUpdate(StaticEnes,enemyno_positionN,enemyno_positionL):
    if len(StaticEnes)==0:  #无目标机
        return
    dellist = []  #需要从StaticEnes删除的名单no   添加均在负载水平部分
    for k,v in StaticEnes.items():
        if k not in enemyno_positionN.keys(): #该机坠毁
            dellist.append(k)
            continue
            # del StaticEnes[k]
        if [enemyno_positionN[k][0],enemyno_positionN[k][1]]!=[enemyno_positionL[k][0],enemyno_positionL[k][1]]:  #水平位置改变了，则从静止字典中删除
            dellist.append(k)
            continue
            # del StaticEnes[k]
    for i in dellist:
        if i in StaticEnes.keys():
            del StaticEnes[i]



