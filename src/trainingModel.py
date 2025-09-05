from sklearn.preprocessing import OrdinalEncoder
from sklearn.model_selection import train_test_split
import pandas as pd
from matplotlib import pyplot as plt
import seaborn as sns

pd.set_option('display.max_columns', None)

df = pd.read_csv('../data/matches.csv')

df = df.sort_values('win', ascending=False)
win = [False, True]

enc = OrdinalEncoder(categories = [win])

df['win'] = enc.fit_transform(df[['win']])

plt.scatter(df.first_serve_pctg, df.win)

plt.scatter(df.second_serve_pctg, df.win)

sns.countplot(x='win', data=df)

xiloc=df.iloc[:, 2:3]
x=df.loc[:,'Player']
y=df['win']

x_train, x_test, y_train, y_test = train_test_split(x, y, train_size=0.8, random_state=42)

print(df)
print(xiloc)
print(x)