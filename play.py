import train, train_y
import pickle
import theano
import theano.tensor as T
import math
import chess, chess.pgn
from parse_game import bb2array
import heapq
import time

def get_model_from_pickle(fn):
    f = open(fn)
    Ws, bs = pickle.load(f)
    
    Ws_s, bs_s = train.get_parameters(Ws=Ws, bs=bs)
    x, p = train.get_model(Ws_s, bs_s)
    
    predict = theano.function(
        inputs=[x],
        outputs=p)

    return predict

class Node(object):
    def __init__(self, gn=None, score=None):
        self.gn = gn
        self.children = []
        self.score = score

def search(heap, move_func, eval_func):
    ''' Traverse game tree in the order of probability '''

    sum_pos = 0.0

    t0 = time.time()
    # while time.time() - t0 < 10.0 and len(heap) > 0:
    for i in xrange(1):
        neg_ll, n_current = heapq.heappop(heap)
        sum_pos += math.exp(-neg_ll)
        # print sum_pos, len(heap)

        b = n_current.gn.board()
        if b.is_checkmate():
            if b.turn == 0:
                n_current.score = float('-inf')
            else:
                n_current.score = float('inf')
        elif b.is_stalemate():
            n_current.score = 0.0

        gn_candidates = []
        X = []
        for move in n_current.gn.board().legal_moves:
            gn_candidate = chess.pgn.GameNode()
            gn_candidate.parent = n_current.gn
            gn_candidate.move = move
            gn_candidates.append(gn_candidate)
            b = gn_candidate.board()
            flip = bool(b.turn == 0)
            X.append(bb2array(b, flip=flip))

        if len(X) == 0:
            # TODO: should treat checkmate
            continue

        # Use model to predict scores
        move_scores = move_func(X)
        eval_scores = [x for x in move_scores] # eval_func(X)

        move_scores *= 0.75 # some smoothing heuristic to make it less confident

        # print 'inserting scores into heap'
        move_scores -= max(move_scores)
        log_z = math.log(sum([math.exp(s) for s in move_scores]))
        move_scores -= log_z

        for gn_candidate, move_score, eval_score in zip(gn_candidates, move_scores, eval_scores):
            n_candidate = Node(gn_candidate, eval_score)
            n_current.children.append(n_candidate)
            heapq.heappush(heap, (neg_ll - move_score, n_candidate))


def minimax(n, level=0):
    score = None
    n.best_child = None

    if level % 2 == 0:
        f = -1
    else:
        f = 1
        
    if n.children:
        for n_child in n.children:
            score_child, _ = minimax(n_child, level+1)
            if score_child:
                if score is None or score_child * f < score * f:
                    score = score_child
                    n.best_child = n_child

    if score is None:
        # Use leaf value
        score = n.score

    if level < 99:
        print '\t' * level, level, score, n.score, n.gn.move
        
    return score, n.best_child

class Player(object):
    def move(self, gn_current):
        raise NotImplementedError()


class Computer(Player):
    def __init__(self, move_func, eval_func):
        self._move_func = move_func
        self._eval_func = eval_func

    def move(self, gn_current):
        assert(gn_current.board().turn == 0)
        n_root = Node(gn=gn_current)
        heap = []
        heap.append((0.0, n_root))
    
        search(heap, self._move_func, self._eval_func)
        
        print 'performing minimax'
        score, best_child = minimax(n_root)
        print 'score:', score
        #print 'most likely event of moves'
        #n = n_root
        #while n is not None:
        #    print n.score
        #    print n.gn.board()
        #    print
        #    n = n.best_child

        print best_child.gn.move
        return best_child.gn

class Human(Player):
    def move(self, gn_current):
        bb = gn_current.board()

        print bb

        def get_move(move_str):
            try:
                move = chess.Move.from_uci(move_str)
            except:
                print 'cant parse'
                return False
            if move not in bb.legal_moves:
                print 'not a legal move'
                return False
            else:
                return move

        while True:
            print 'your turn:'
            move = get_move(raw_input())
            if move:
                break

        gn_new = chess.pgn.GameNode()
        gn_new.parent = gn_current
        gn_new.move = move
        
        print gn_new.board()
        return gn_new

class Sunfish(Player):
    def __init__(self):
        import sunfish
        self._pos = sunfish.Position(sunfish.initial, 0, (True,True), (True,True), 0, 0)

    def move(self, gn_current):
        import sunfish

        assert(gn_current.board().turn == 1)

        # Apply last_move
        crdn = str(gn_current.move)
        move = (sunfish.parse(crdn[0:2]), sunfish.parse(crdn[2:4]))
        self._pos = self._pos.move(move)            

        move, score = sunfish.search(self._pos)
        self._pos = self._pos.move(move)

        crdn = sunfish.render(119-move[0]) + sunfish.render(119 - move[1])
        print crdn
        move = chess.Move.from_uci(crdn)
        
        gn_new = chess.pgn.GameNode()
        gn_new.parent = gn_current
        gn_new.move = move

        return gn_new

def play():
    move_func = get_model_from_pickle('model.pickle')
    eval_func = move_func # get_model_from_pickle('model_y.pickle')

    gn_current = chess.pgn.Game()

    player_a = Computer(move_func, eval_func)
    player_b = Sunfish()

    while True:
        gn_current = player_a.move(gn_current)
        print '=========== Player A:', gn_current.move
        print gn_current.board()
        gn_current = player_b.move(gn_current)
        print '=========== Player B:', gn_current.move
        print gn_current.board()

        
if __name__ == '__main__':
    play()
