# Team Name: BagelBytes

This bot makes its moves based on 3 priorities:
    1. Capture the opponent's king 
    2. Get out of check if a piece is in check 
    3. Revert to the stockfish engine to choose the best move


##Requirements 

Stockfish:
    Download stockfish onto your local environment: https://stockfishchess.org/
    
    Create an environment variable called STOCKFISH_EXECUTABLE that has the path to the Stockfish executable. 

Reconchess: 
    Install the reconchess package.
   ` pip install reconchess`
    