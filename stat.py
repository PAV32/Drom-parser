import pandas as pd

df = pd.read_csv('cars_note_RF.csv', sep = ';')

#print (df.head())

df['Categor'] = None
df.loc[df['Descriptio'].str.contains('1.2 X', case=False, na = False), 'Categor'] = '1.2 X'
df.loc[df['Descriptio'].str.contains('1.2 e-Power', case=False, na = False), 'Categor'] = '1.2 e-Power'
df_clean = df.dropna (subset='Categor')

print(len(df_clean))
print (df_clean.head())

df_clean = df_clean[df_clean['Price'] > 0]

result = df_clean.groupby(['Local', 'Categor']).agg(Средняя_цена=('Price', 'mean'),
                                                        Кол_во_машин = ('Price', 'count')).reset_index()

result['Средняя_цена'] = result['Средняя_цена'].round(0).astype(int)

result = result.sort_values(by = ['Local', 'Средняя_цена'], ascending=[True,False])



print('Средняя цена')
print(result)

result.to_csv('result_note_RF.csv', sep = ';', index = False, encoding = 'utf-8-sig')