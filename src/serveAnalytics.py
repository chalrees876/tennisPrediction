import pandas as pd
import main

#create serve dataframe
#record stats of any match that is input
serve_events = main.main()

df = serve_events.create_el_df()

print(df.head())

