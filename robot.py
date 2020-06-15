import copy
import random
from reconchess import *
import chess.engine
import os

STOCKFISH_ENV_VAR = 'STOCKFISH_EXECUTABLE'


class IsaacBot(Player):
    def __init__(self):
        # set up some useful variables on a game-wide scale
        self.enemies = None
        # i've been phasing this out slowly, replacing with the self.boards thing
        self.board = None
        self.color = None
        self.my_piece_captured_square = None
        # this is basically a list of all possible positions the board could be in at any given point
        self.boards = None
        self.count = 0
        if STOCKFISH_ENV_VAR not in os.environ:
            raise KeyError(
                'TroutBot requires an environment variable called "{}" pointing to the Stockfish executable'.format(
                    STOCKFISH_ENV_VAR))

            # make sure there is actually a file
        stockfish_path = os.environ[STOCKFISH_ENV_VAR]
        if not os.path.exists(stockfish_path):
            raise ValueError('No stockfish executable found at "{}"'.format(stockfish_path))

        # initialize the stockfish engine
        self.engine = chess.engine.SimpleEngine.popen_uci(stockfish_path, setpgrp=True)

    def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
        self.board = board
        self.color = color
        # start the board list with just one - a copy of the starting board
        self.boards = [board.copy()]

    def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[Square]):
        if self.count == 0 and self.color:
            # this is just to see if it's the first turn and we're white
            # if we are, skip handling opponent's move (no move to handle)
            self.count = 1
        else:
            print("my turn! lets see what happened")
            self.my_piece_captured_square = capture_square
            if captured_my_piece:
                print("i got got")
                self.board.remove_piece_at(capture_square)
                # make a copy because if we looped through self.boards, we couldn't delete
                bs = copy.deepcopy(self.boards)
                for b in bs:
                    if not b.attackers(not self.color, capture_square):
                        # if the attack wasn't possible on a certain board, it must not have been the real board
                        self.boards.remove(b)
                    else:
                        # if the attack was possible, make a new board for each way it could have happened
                        # maybe a knight or pawn both could have taken my piece - account for both
                        for ater in b.attackers(not self.color, capture_square):
                            nb = b.copy()
                            nb.push(chess.Move(ater, capture_square))
                            self.boards.append(nb)
                        # delete the original board after branches are accounted for
                        self.boards.remove(b)
            else:
                # if there was no attack
                bs = copy.deepcopy(self.boards)
                for b in self.boards:
                    # it's possible the opponent took no move at all
                    b.push(chess.Move.null())
                for b in bs:
                    # for each board, add to the list a new board for each possible move the opponent might have taken
                    for m in b.pseudo_legal_moves:
                        if not b.is_capture(m):
                            nb = b.copy()
                            nb.push(m)
                            self.boards.append(nb)
            print("there are", len(self.boards), "possible boards")
            print("removing duplicate boards")
            # two paths of moves can lead to the same board, so remove duplicates
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
        # picking an edge is a bad idea because you get a three by three square, so remove those as options
        for square, piece in self.board.piece_map().items():
            if piece.color == self.color:
                sense_actions.remove(square)
            elif chess.square_file(square) == 0 or chess.square_file(square) == 7:
                sense_actions.remove(square)
            elif chess.square_rank(square) == 0 or chess.square_rank(square) == 7:
                sense_actions.remove(square)
        # this list will measure "entropy" - basically, how much uncertainty we could remove with a given sense
        ents = [0] * 64
        max_act = sense_actions[0]
        for i in range(64):
            # tally up how many boards say a certain piece is at this spot
            # might look like this:
            # empty: 12 votes
            # pawn: 3 votes
            # knight: 5 votes. etc
            piece_dict = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0}
            for b in self.boards:
                if b.piece_type_at(i) is None:
                    piece_dict[7] += 1
                else:
                    piece_dict[b.piece_type_at(i)] += 1
            max_p = 0
            # find the highest vote count among the pieces
            for p in piece_dict:
                if piece_dict[p] > max_p:
                    max_p = piece_dict[p]
            # the entropy is one minus the percentage of boards which voted for that piece
            if len(self.boards) > 0:
                ents[i] = 1 - max_p / len(self.boards)
            else:
                ents[i] = 0
        max_ent = -1
        # find the spot to sense with the highest total entropy among its 9 squares
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
        # keep only the boards which reflect our new knowledge
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
            # say we've "found the king" if the probability he's on this square is > .5
            if king_dict[square] > .5:
                enemy_king_square = square
        if enemy_king_square >= 0:
            print("found the king. probability he's here: ", king_dict[enemy_king_square])
            # likelihood dictionary - probability that a move would take the king
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
            # take the king only if there's a >50% chance it will work
            if maxlik > .5:
                print("attempting king attack. prob =", maxlik)
                return best_move
            else:
                print("none king attacks strong enough. moving on")
        # 2nd priority - if in check, get out
        check_count = 0
        check_board_list = []
        for b in self.boards:
            if b.is_check():
                check_count += 1
                check_board_list.append(b.copy())
        check_prob = check_count / len(self.boards)
        # if more than 2% of possible boards say we're in check, do something about it
        if check_prob > .02:
            print("might be in check. prob=", check_prob)
            try:
                move_dict = {}
                for move in move_actions:
                    move_dict[move] = 0
                for board in check_board_list:
                    if board.is_valid():
                        result = self.engine.play(board, chess.engine.Limit(time=0.1), root_moves=move_actions)
                        if result is not None:
                            move_dict[result.move] += 1
                best_move = ''
                max_votes = -1
                for move in move_dict:
                    if move_dict[move] > max_votes:
                        max_votes = move_dict[move]
                        best_move = move
                print("stockfish says", best_move, "is the best move with", max_votes, "votes")
                return best_move
            except chess.engine.EngineTerminatedError:
                print('Stockfish Engine died')
            except chess.engine.EngineError:
                print('Stockfish Engine bad state at "{}"'.format(self.board.fen()))

        else:
            print("probably not in check. prob:", check_prob)
        # ask stockfish what to do
        try:
            move_dict = {}
            for move in move_actions:
                move_dict[move] = 0
            for board in self.boards:
                if board.is_valid():
                    result = self.engine.play(board, chess.engine.Limit(time=0.1), root_moves=move_actions)
                    if result is not None:
                        move_dict[result.move] += 1
            best_move = ''
            max_votes = -1
            for move in move_dict:
                if move_dict[move] > max_votes:
                    max_votes = move_dict[move]
                    best_move = move
            print("stockfish says", best_move, "is the best move with", max_votes, "votes")
            return best_move
        except chess.engine.EngineTerminatedError:
            print('Stockfish Engine died')
        except chess.engine.EngineError:
            print('Stockfish Engine bad state at "{}"'.format(self.board.fen()))

    def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
                           captured_opponent_piece: bool, capture_square: Optional[Square]):
        if captured_opponent_piece:
            print("i caught someone!")
            bs = copy.deepcopy(self.boards)
            # if a board didn't expect a piece to be there, it wasn't correct
            for b in bs:
                if b.color_at(capture_square) == self.color or b.color_at(capture_square) is None:
                    self.boards.remove(b)
        elif taken_move is not None:
            # if a board expected a capture but we didn't, it was wrong
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
            # update all boards
            for b in self.boards:
                b.push(taken_move)
        else:
            # if our move failed
            print("uh oh")
            bs = copy.deepcopy(self.boards)
            for b in bs:
                if b.is_pseudo_legal(requested_move):
                    self.boards.remove(b)
            for b in self.boards:
                # this is to update their turn counters
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
        try:
            # if the engine is already terminated then this call will throw an exception
            self.engine.quit()
        except chess.engine.EngineTerminatedError:
            pass
