import pandas as pd
from src.main import main as serve_df_creator
from natsort import natsort_keygen


serve_event_logger = serve_df_creator('Roland_Garros-SF-Novak_Djokovic')

serve_df = serve_event_logger.create_serve_df()

sorted_df = serve_df.sort_values(by=['Point Id'], key=natsort_keygen())

print(sorted_df)

player1, player2 = serve_event_logger.get_players()

first_serves_made = sorted_df[(sorted_df['Serve Num'] == 1) & (sorted_df['Is Fault'] == False)]

p1_first_serves_made = len(first_serves_made[first_serves_made['Server'] == player1])
p2_first_serves_made = len(first_serves_made[first_serves_made['Server'] == player2])
p1_total_first_serves = len(sorted_df[(sorted_df['Server'] == player1) & (sorted_df['Serve Num'] == 1)])
p2_total_first_serves = len(sorted_df[(sorted_df['Server'] == player2) & (sorted_df['Serve Num'] == 1)])
p1_first_serve_percentage = p1_first_serves_made / p1_total_first_serves * 100
p2_first_serve_percentage = p2_first_serves_made / p2_total_first_serves * 100

print(player1, "first serve percent", p1_first_serve_percentage)
print(player2, "first serve percent", p2_first_serve_percentage)