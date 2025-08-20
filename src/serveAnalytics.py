import pandas as pd
import main

#create serve dataframe
#record stats of any match that is input
columns = ["Serve Direction", "Serve Num", "Is Fault", "Miss Type", "Is Ace", "SNV", "Match Id", "Point Id", "Set Score", "Game Score", "Point Score", "Server", "Returner", "Point Winner"]
serve_events = main.main()

serve_events.print()

df = pd.DataFrame(serve_events, columns=columns)

