import sys
import random
import heapq

from src.player import *
from src.structure import *
from src.game_constants import GameConstants as GC

infty = 1000000000
cardinal_directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
tower_range = [(-2,0),(-1,-1),(-1,0),(-1,1),(0,-2),(0,-1),(0,0),(0,1),(0,2),(1,-1),(1,0),(1,1),(2,0)]
EMPTY_STRUCT = 0
ALLY_STRUCT = 1
ENEMY_STRUCT = 2

EMPTY_TYPE = 0
ROAD_TYPE = 1
TOWER_TYPE = 2
GENERATOR_TYPE = 3

EARLYGAME_ROUNDS = 20

class MyPlayer(Player):
    def __init__(self):
        return

    def in_bounds(self, x, y):
        return 0 <= x < self.MAP_WIDTH and 0 <= y < self.MAP_HEIGHT

    def passable(self, x, y):
        if self.structmap == None:
            return self.in_bounds(x, y) and self.map[x][y].structure == None
        else:
            return self.in_bounds(x, y) and self.structmap[x][y] == EMPTY_STRUCT

    def dijkstra(self, sources, dist, prev=None):
        vis = [ [ False ] * self.MAP_HEIGHT for i in range(self.MAP_WIDTH) ]
        pq = []
        for x in range(self.MAP_WIDTH):
            for y in range(self.MAP_HEIGHT):
                dist[x][y] = infty
        for (x,y) in sources:
            dist[x][y] = 0
            heapq.heappush(pq, (0,(x,y)))
        while len(pq) != 0:
            (d,(x,y)) = heapq.heappop(pq)
            if vis[x][y]:
                continue
            vis[x][y] = True
            for (dx,dy) in cardinal_directions:
                nx = x + dx
                ny = y + dy
                if self.passable(nx, ny):
                    w = self.map[nx][ny].passability
                    if dist[nx][ny] > dist[x][y] + w:
                        dist[nx][ny] = dist[x][y] + w
                        if prev is not None:
                            prev[nx][ny] = (x, y)
                        heapq.heappush(pq, (dist[nx][ny], (nx,ny)))
    
    def calc_targets(self):
        # Compute distances to ally locations
        ally_sources = []
        enemy_sources = []
        for x in range(self.MAP_WIDTH):
            for y in range(self.MAP_HEIGHT):
                st = self.map[x][y].structure
                if st is not None:
                    if st.team == self.player_info.team:
                        ally_sources.append((st.x, st.y))
        self.ally_dist = [ [ infty ] * self.MAP_HEIGHT for i in range(self.MAP_WIDTH) ]
        self.build_prev = [ [ None ] * self.MAP_HEIGHT for i in range(self.MAP_WIDTH) ]
        self.dijkstra(ally_sources, self.ally_dist, self.build_prev)

        self.targets = []
        costs = [ [0] * self.MAP_HEIGHT for i in range(self.MAP_WIDTH) ]
        location_scores = [ [0] * self.MAP_HEIGHT for i in range(self.MAP_WIDTH) ]
        population_scores = [ [0] * self.MAP_HEIGHT for i in range(self.MAP_WIDTH) ]
        for x in range(self.MAP_WIDTH):
            for y in range(self.MAP_HEIGHT):
                if self.map[x][y].structure is not None:
                    # can't build here
                    continue
                total_population = 0
                for (dx,dy) in tower_range:
                    nx = x + dx
                    ny = y + dy
                    if self.in_bounds(nx, ny):
                        total_population += self.populations[nx][ny]
                location_score = 0
                if self.turn_num < EARLYGAME_ROUNDS:
                    # early game
                    location_score = 1 - abs(self.enemy_generator_dist[x][y] - 1.2*self.ally_generator_dist[x][y]) / (self.MAP_WIDTH + self.MAP_HEIGHT)
                else:
                    # late game
                    location_score = 1 - self.ally_dist[x][y] / (self.MAP_WIDTH + self.MAP_HEIGHT)
                population_scores[x][y] = total_population / (len(tower_range) * 10)
                costs[x][y] = self.ally_dist[x][y]*StructureType.ROAD.get_base_cost() + self.map[x][y].passability*StructureType.TOWER.get_base_cost()
                location_scores[x][y] = location_score
        cost_max = 0
        for x in range(self.MAP_WIDTH):
            for y in range(self.MAP_HEIGHT):
                cost_max = max(cost_max, costs[x][y])
        for x in range(self.MAP_WIDTH):
            for y in range(self.MAP_HEIGHT):
                costs[x][y] /= cost_max
                costs[x][y] = 1 - costs[x][y]

        candidates = []
        for x in range(self.MAP_WIDTH):
            for y in range(self.MAP_HEIGHT):
                if self.map[x][y].structure is not None:
                    # can't build here
                    continue
                if population_scores[x][y] == 0:
                    continue
                if self.ally_dist[x][y] >= infty * 0.5:
                    continue
                score = 5*population_scores[x][y] + costs[x][y] + location_scores[x][y]
                candidates.append((score, (x,y)))
        list.sort(candidates, reverse=True)
        self.targets = []
        for (score,(x,y)) in candidates:
            self.targets.append((x,y))
    
    def real_init(self):
        self.MAP_WIDTH = len(self.map)
        self.MAP_HEIGHT = len(self.map[0])

        # Find our generators
        self.ally_generators = []
        self.enemy_generators = []
        for x in range(self.MAP_WIDTH):
            for y in range(self.MAP_HEIGHT):
                st = self.map[x][y].structure
                # check the tile is not empty
                if st is not None:
                    if st.team == self.player_info.team:
                        self.ally_generators.append((st.x, st.y))
                    else:
                        self.enemy_generators.append((st.x, st.y))
        self.ally_generator_dist = [ [ infty ] * self.MAP_HEIGHT for i in range(self.MAP_WIDTH) ]
        self.dijkstra(self.ally_generators, self.ally_generator_dist)
        self.enemy_generator_dist = [ [ infty ] * self.MAP_HEIGHT for i in range(self.MAP_WIDTH) ]
        self.dijkstra(self.enemy_generators, self.enemy_generator_dist)

        self.populations = [ [ 0 ] * self.MAP_HEIGHT for i in range(self.MAP_WIDTH) ]
        for x in range(self.MAP_WIDTH):
            for y in range(self.MAP_HEIGHT):
                self.populations[x][y] = self.map[x][y].population

    
    def can_build(self, raw_cost, x, y):
        if not self.passable(x,y):
            return False
        if self.money < raw_cost * self.map[x][y].passability:
            return False
        for (dx,dy) in cardinal_directions:
            nx = x + dx
            ny = y + dy
            if not self.in_bounds(nx, ny):
                continue
            if self.structmap[nx][ny] == ALLY_STRUCT:
                return True
        return False
    
    def try_build(self, sttype, x, y):
        if not self.can_build(sttype.get_base_cost(), x, y):
            return
        if sttype == StructureType.TOWER:
            tot = 0
            for (dx,dy) in tower_range:
                nx = x + dx
                ny = y + dy
                if self.in_bounds(nx,ny):
                    tot += self.populations[nx][ny]
            if tot == 0:
                return
        self.build(sttype, x, y)
        self.structmap[x][y] = ALLY_STRUCT
        if sttype == StructureType.TOWER:
            self.typemap[x][y] = TOWER_TYPE
            for (dx,dy) in tower_range:
                nx = x + dx
                ny = y + dy
                if self.in_bounds(nx,ny):
                    self.populations[nx][ny] = 0
        else:
            self.typemap[x][y] = ROAD_TYPE
        self.money -= sttype.get_base_cost() * self.map[x][y].passability
    
    def build_towards(self, x, y):
        locs = []
        cur = (x, y)
        while cur is not None:
            locs.append(cur)
            cur = self.build_prev[cur[0]][cur[1]]
        locs.reverse()
        for (locx, locy) in locs:
            if (locx, locy) == (x,y):
                self.try_build(StructureType.TOWER, locx, locy)
            else:
                threshold = self.map[self.targets[0][0]][self.targets[0][1]].passability * StructureType.TOWER.get_base_cost()
                if self.turn_num < EARLYGAME_ROUNDS:
                    threshold = 0
                if self.money >= threshold:
                    self.try_build(StructureType.ROAD, locx, locy)
    
    def block_resources(self, cost_limit=infty):
        # sort by distance to resource locs
        block_locs = []
        for x in range(self.MAP_WIDTH):
            for y in range(self.MAP_HEIGHT):
                if self.passable(x, y) and self.ally_dist[x][y] < infty:
                    # block population centers that we control
                    near_pop = False
                    for (dx,dy) in tower_range:
                        nx = x + dx
                        ny = y + dy
                        if self.in_bounds(nx,ny):
                            if self.map[nx][ny].population > 0 and self.populations[nx][ny] == 0:
                                near_pop = True
                                break
                    if near_pop:
                        block_locs.append((x,y))

        # build roads everywhere
        cost = 0
        for (x,y) in block_locs:
            if self.can_build(StructureType.ROAD.get_base_cost(), x, y):
                cur_cost = StructureType.ROAD.get_base_cost() * self.map[x][y].passability
                if cost + cur_cost > cost_limit:
                    continue
                self.try_build(StructureType.ROAD, x, y)
    
    def build_towers(self):
        locs = []
        for x in range(self.MAP_WIDTH):
            for y in range(self.MAP_HEIGHT):
                if self.can_build(StructureType.TOWER.get_base_cost(), x, y):
                    total_population = 0
                    for (dx,dy) in tower_range:
                        nx = x + dx
                        ny = y + dy
                        if self.in_bounds(nx, ny):
                            total_population += self.populations[nx][ny]
                    if total_population > 0:
                        locs.append((total_population, (x,y)))
        locs.sort(reverse=True)
        for (p,(x,y)) in locs:
            self.try_build(StructureType.TOWER, x, y)
    
    def play_turn(self, turn_num, map, player_info):
        self.turn_num = turn_num
        self.map = map
        self.player_info = player_info
        self.structmap = None

        if (self.turn_num == 0):
            self.real_init()

        self.structmap = [ [EMPTY_STRUCT]*self.MAP_HEIGHT for i in range(self.MAP_WIDTH) ]
        self.typemap = [ [EMPTY_TYPE]*self.MAP_HEIGHT for i in range(self.MAP_WIDTH) ]
        for x in range(self.MAP_WIDTH):
            for y in range(self.MAP_HEIGHT):
                st = self.map[x][y].structure
                if st == None:
                    self.structmap[x][y] = EMPTY_STRUCT
                    self.typemap[x][y] = EMPTY_TYPE
                else:
                    # team
                    if st.team == self.player_info.team:
                        self.structmap[x][y] = ALLY_STRUCT
                    else:
                        self.structmap[x][y] = ENEMY_STRUCT
                    # type
                    if st.type == StructureType.TOWER:
                        self.typemap[x][y] = TOWER_TYPE
                    elif st.type == StructureType.ROAD:
                        self.typemap[x][y] = ROAD_TYPE
                    elif st.type == StructureType.GENERATOR:
                        self.typemap[x][y] = GENERATOR_TYPE

        if (self.turn_num % 1 == 0):
            self.calc_targets()

        self.money = player_info.money

        if len(self.targets) == 0:
            # greedily build roads close to resources
            self.block_resources()
        else:
            # build paths
            self.build_towards(self.targets[0][0], self.targets[0][1])
            
            # build towers
            self.build_towers()
            
            if self.turn_num >= 120:
                self.block_resources(50)

        return
