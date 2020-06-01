import copy
import random
from reconchess import *


class IsaacBot(Player):
    def __init__(self):
        self.enemies = None
        self.board = None
        self.color = None
        self.my_piece_captured_square = None
        self.boards = None
        self.count = 0

    def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
        self.board = board
        self.color = color
        self.boards = [board.copy()]

    def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[Square]):
        if self.count == 0 and self.color:
            self.count = 1
        else:
            print("my turn! lets see what happened")
            self.my_piece_captured_square = capture_square
            if captured_my_piece:
                print("i got got")
                self.board.remove_piece_at(capture_square)
                bs = copy.deepcopy(self.boards)
                for b in bs:
                    if not b.attackers(not self.color, capture_square):
                        self.boards.remove(b)
                    else:
                        for ater in b.attackers(not self.color, capture_square):
                            nb = b.copy()
                            nb.push(chess.Move(ater, capture_square))
                            self.boards.append(nb)
                        self.boards.remove(b)
            else:
                bs = copy.deepcopy(self.boards)
                for b in self.boards:
                    b.push(chess.Move.null())
                for b in bs:
                    for m in b.pseudo_legal_moves:
                        nb = b.copy()
                        nb.push(m)
                        self.boards.append(nb)
            print("there are", len(self.boards), "possible boards")
            print("removing duplicate boards")
            sb = set(b.fen() for b in self.boards)
            self.boards = []
            for b in sb:
                bd = chess.Board()
                bd.set_fen(b)
                self.boards.append(bd)
            print("there are", len(self.boards), "possible boards")

    def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> \
            Optional[Square]:
        print("picking spot to look")
        for square, piece in self.board.piece_map().items():
            if piece.color == self.color:
                sense_actions.remove(square)
            elif chess.square_file(square) == 0 or chess.square_file(square) == 7:
                sense_actions.remove(square)
            elif chess.square_rank(square) == 0 or chess.square_rank(square) == 7:
                sense_actions.remove(square)
        ents = [0] * 64
        max_act = sense_actions[0]
        for i in range(64):
            piece_dict = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0}
            for b in self.boards:
                if b.piece_type_at(i) is None:
                    piece_dict[7] += 1
                else:
                    piece_dict[b.piece_type_at(i)] += 1
            max_p = 0
            for p in piece_dict:
                if piece_dict[p] > max_p:
                    max_p = piece_dict[p]
            if len(self.boards) > 0:
                ents[i] = 1 - max_p / len(self.boards)
            else:
                ents[i] = 0
        max_ent = -1
        for act in sense_actions:
            if 7 < act < 56 and act % 8 != 0 and act % 8 != 7:
                ent = ents[act] + ents[act - 1] + ents[act + 1]
                ent += ents[act - 7] + ents[act - 8] + ents[act - 9]
                ent += ents[act + 7] + ents[act + 8] + ents[act + 9]
                if ent > max_ent:
                    max_ent = ent
                    max_act = act
        print("found a spot. entropy is", max_ent)
        return max_act

    def handle_sense_result(self, sense_result: List[Tuple[Square, Optional[chess.Piece]]]):
        print("updating boards")
        bs = copy.deepcopy(self.boards)
        for b in bs:
            if b is None:
                self.boards.remove(b)
            else:
                for square, piece in sense_result:
                    pt = b.piece_type_at(square)
                    if piece is not None and pt != piece.piece_type:
                        self.boards.remove(b)
                        break
                    elif piece is not None and b.color_at(square) != piece.color:
                        self.boards.remove(b)
                        break
                    elif piece is None and pt is not None:
                        self.boards.remove(b)
                        break
        print("there are", len(self.boards), "possible boards")

    def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
        # if the boards got screwed up we're screwed
        if len(self.boards) == 0:
            return random.choice(move_actions)
        # first priority - if king can be gotten, get him
        king_dict = {}
        for i in range(64):
            king_dict[i] = 0
        for b in self.boards:
            if b.king(not self.color) is not None:
                king_dict[b.king(not self.color)] += 1
        enemy_king_square = -1
        for square in king_dict:
            king_dict[square] = king_dict[square]/len(self.boards)
            if king_dict[square] > .5:
                enemy_king_square = square
        if enemy_king_square >= 0:
            print("found the king. probability he's here: ", king_dict[enemy_king_square])
            # if there are any ally pieces that can take king, execute one of those moves
            lik_dict = {}
            for move in move_actions:
                lik_dict[move] = 0
                if move.to_square == enemy_king_square:
                    for b in self.boards:
                        if b.is_pseudo_legal(move):
                            lik_dict[move] += 1
                lik_dict[move] = lik_dict[move] / len(self.boards)
            maxlik = 0
            best_move = ''
            for move in lik_dict:
                if lik_dict[move] > maxlik:
                    maxlik = lik_dict[move]
                    best_move = move
            if maxlik > .5:
                print("attempting king attack. prob =", maxlik)
                return best_move
            else:
                print("none king attacks strong enough. moving on")
        # 2nd priority - if in check, get out
        check_count = 0
        for b in self.boards:
            if b.is_check():
                check_count += 1
        check_prob = check_count / len(self.boards)
        if check_prob > .05:
            print("might be in check. prob=", check_prob)
            move_dict = {}
            for move in move_actions:
                move_dict[move] = 0
                for b in self.boards:
                    if b.is_legal(move):
                        move_dict[move] += 1
                        if b.is_capture(move):
                            move_dict[move] += .5
            m = -1
            bm = ''
            for move in move_dict:
                if move_dict[move] > m:
                    m = move_dict[move]
                    bm = move
            print("gonna attempt to get out of check")
            return bm
        else:
            print("probably not in check. prob:", check_prob)
        # 3rd priority - make check happen
        check_dict = {}
        for move in move_actions:
            check_dict[move] = 0
            for b in self.boards:
                if b.is_pseudo_legal(move) and b.gives_check(move):
                    check_dict[move] += 1
                    b.push(move)
                    if b.is_checkmate():
                        check_dict[move] += 1
                    b.pop()
            check_dict[move] /= len(self.boards)
        ma = 0
        bm = ''
        for m in check_dict:
            if check_dict[m] > ma:
                ma = check_dict[m]
                bm = m
        if ma > .5:
            print("attempting to check. prob =", ma)
            return bm

        # 4th priority - attack
        am = None
        max_lik = 0
        for move in move_actions:
            lik = 0
            for b in self.boards:
                if b.is_legal(move) and b.color_at(move.to_square) == (not self.color):
                    lik += 1
            if lik/len(self.boards) > max_lik:
                max_lik = lik/len(self.boards)
                am = move
        if am is not None and max_lik > .5:
            print("gonna try to attack! Likelihood =", max_lik)
            return am
        # 5th priority - random from most likely to be legal
        print("most likely to succeed in high school move")
        d = {}
        for move in move_actions:
            lik = 0
            for b in self.boards:
                if b.is_legal(move):
                    lik += 2
                elif b.is_pseudo_legal(move):
                    lik += 1
            d[move] = lik
        maxi = max(d.values())
        ms = []
        for m in d:
            if d[m] == maxi:
                ms.append(m)
        return random.choice(ms)

    def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
                           captured_opponent_piece: bool, capture_square: Optional[Square]):
        if captured_opponent_piece:
            print("i caught someone!")
            bs = copy.deepcopy(self.boards)
            for b in bs:
                if b.color_at(capture_square) == self.color or b.color_at(capture_square) is None:
                    self.boards.remove(b)
        elif taken_move is not None:
            bs = copy.deepcopy(self.boards)
            for b in bs:
                if b.is_capture(taken_move):
                    self.boards.remove(b)
        if taken_move != requested_move:
            print("took a diff move than i wanted")
            bs = copy.deepcopy(self.boards)
            for b in bs:
                if b.is_pseudo_legal(requested_move):
                    self.boards.remove(b)
        if taken_move is not None:
            bs = copy.deepcopy(self.boards)
            for b in bs:
                if not b.is_pseudo_legal(taken_move):
                    self.boards.remove(b)
            for b in self.boards:
                b.push(taken_move)
        else:
            print("uh oh")
            bs = copy.deepcopy(self.boards)
            for b in bs:
                if b.is_pseudo_legal(requested_move):
                    self.boards.remove(b)
            for b in self.boards:
                b.push(chess.Move.null())
        print("there are", len(self.boards), "possible boards")
        if len(self.boards) == 1:
            self.board = self.boards[0]

    def handle_game_end(self, winner_color: Optional[Color], win_reason: Optional[WinReason],
                        game_history: GameHistory):
        if winner_color == self.color:
            print("i won!")
        else:
            print("i did not win")
        pass
