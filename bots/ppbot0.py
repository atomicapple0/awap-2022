import sys
import random
import heapq

from src.player import *
from src.structure import *
from src.game_constants import GameConstants as GC

infty = 1000000000
cardinal_directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
tower_range = [(-2,0),(-1,-1),(-1,0),(-1,1),(0,-2),(0,-1),(0,0),(0,1),(0,2),(1,-1),(1,0),(1,1),(2,0)]
tower_cost = 250
road_cost = 10

class MyPlayer(Player):
    def __init__(self):
        return

    def in_bounds(self, x, y):
        return 0 <= x < self.MAP_WIDTH and 0 <= y < self.MAP_HEIGHT

    def passable(self, x, y):
        return self.in_bounds(x, y) and self.map[x][y].structure is None

    def dijkstra(self, sources, dist, prev=None):
        '''priority_queue<pi, vector<pi>, greater<pi>> pq;
        M00(i, SZ) d[i] = inf;
        d[u] = 0;
        pq.push(mp(0, u));
        while(!pq.empty()) {
            pi t = pq.top(); pq.pop();
            if(vis[t.s]) continue;
            vis[t.s] = 1;

            for(auto v: adj[t.s]) {
                if(d[v.f] > d[t.s] + v.s) {
                    d[v.f] = d[t.s] + v.s;
                    pq.push(mp(d[t.s]+v.s, v.f));
                }
            }
        }'''
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
                            if prev[x][y] == None:
                                prev[nx][ny] = (nx, ny)
                            else:
                                prev[nx][ny] = prev[x][y]
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
        self.build_towards = [ [ None ] * self.MAP_HEIGHT for i in range(self.MAP_WIDTH) ]
        self.dijkstra(ally_sources, self.ally_dist, self.build_towards)

        self.targets = []
        populations = [ [0] * self.MAP_HEIGHT for i in range(self.MAP_WIDTH) ]
        costs = [ [0] * self.MAP_HEIGHT for i in range(self.MAP_WIDTH) ]
        location_scores = [ [0] * self.MAP_HEIGHT for i in range(self.MAP_WIDTH) ]
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
                        total_population += self.map[nx][ny].population
                location_score = 0
                if self.turn_num < 40:
                    # early game
                    location_score = 1 - (self.enemy_generator_dist[x][y] - self.ally_generator_dist[x][y]) / (self.MAP_WIDTH + self.MAP_HEIGHT)
                else:
                    # late game
                    location_score = 1 - self.ally_dist[x][y] / (self.MAP_WIDTH + self.MAP_HEIGHT)
                populations[x][y] = total_population / (len(tower_range) * 10)
                costs[x][y] = self.ally_dist[x][y]*road_cost + self.map[x][y].passability*tower_cost
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
                if populations[x][y] == 0:
                    continue
                score = populations[x][y] + costs[x][y] + location_scores[x][y]
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
            st = self.map[nx][ny].structure
            if st is not None and st.team == self.player_info.team:
                return True
        return False
    
    def play_turn(self, turn_num, map, player_info):
        self.turn_num = turn_num
        self.map = map
        self.player_info = player_info
        self.money = player_info.money

        if (self.turn_num == 0):
            self.real_init()
        if (self.turn_num % 1 == 0):
            self.calc_targets()
        for (x,y) in self.targets:
            if self.can_build(tower_cost, x, y):
                self.build(StructureType.TOWER, x, y)
                self.money -= tower_cost * self.map[x][y].passability
        rem = 5
        for (x,y) in self.targets:
            rem -= 1
            if rem == 0:
                break
            # build towards (x,y)
            if self.build_towards[x][y] is not None:
                (bx, by) = self.build_towards[x][y]
                if self.can_build(road_cost, bx, by):
                    self.build(StructureType.ROAD, bx, by)
                    self.money -= road_cost * self.map[bx][by].passability
        return
