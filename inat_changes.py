import pandas as pd
from datetime import date
import re
import os

print('Enter csv path as \'data/file.csv\' without quotes:')
observations_path = input()
from datetime import date

print('Enter start date. Print \'min\' without quotes for viewing from first observarion day:')
print('Start year:')
begin_year = input()
if begin_year == 'min':
    print('Ok')
else:
    print('Start month as number:')
    begin_month = input()
    print('Start day:')
    begin_day = input()

print('Enter finish date. Print \'max\' without quotes for viewing up to last observation day:')
print('Finish year:')
finish_year = input()
if finish_year == 'max':
    print('Ok')
else:
    print('Finish month as number:')
    finish_month = input()
    print('Finish day:')
    finish_day = input()

if begin_year == 'min':
    start_date = 'min'
else:
    start_date = date(int(begin_year), int(begin_month), int(begin_day))


if finish_year == 'max':
    finish_date = 'max'
else:
    finish_date = date(int(finish_year), int(finish_month), int(finish_day))

csvname = os.path.basename(observations_path)
htmlname = csvname.replace('.','_') + '.html'

def prepare_df(observations_path, start_date, finish_date):
    
    df_full = pd.read_csv(observations_path) #создаём новый огромный датафрейм из csv
    df = df_full[['id','user_login','created_at','quality_grade','scientific_name','common_name']].copy() #создаём новый маленький датафрейм с нужными столбцами
    del(df_full)
    df['created_at'] = pd.to_datetime(df['created_at']).dt.date #конвертируем столбец с датами наблюдений в тип datatime
    if start_date == 'min':
        start_date = min(df['created_at'])
    else:
        pass
    if finish_date == 'max':
        finish_date = max(df['created_at'])
    else:
        pass
    return df, start_date, finish_date


def prepare_to_date(df, date_to):

    #prepare_to_date нужна чтобы создать список "лучших" 
    #наблюдателей с большим количеством наблюдений на определённую дату
    

    stat = pd.DataFrame()                                                               #создаём новый датафрейм
    counts = df[df['created_at']<=date_to].loc[:,'user_login'].value_counts()           #подсчитываем количество всех наблюдений у каждого пользователя с датой предшествующей или равной date_to
    stat['user'] = counts.index                                                         #создаём колонку с именами пользователей
    stat['obs_count'] = counts.to_list()                                                #создаём колонку с кол-вом всех наблюдений
    research = df[(df['quality_grade']=='research')&(df['created_at']<=date_to)].loc[:,'user_login'].value_counts()         #подсчитываем кол-во наблюдений со статусом research у каждого пользователя
    del(df)
    stat = stat.join(research,on='user', how='left')                                    #создаём колонку с кол-вом наблюдений research, объединяя список всех наблюдений со списком наблюдений research
    del(research)
    stat.rename(columns={'user':'user',                                                 #просто нужно переименовать один столбец из-за особенности join
                        'obs_count':'obs_count',
                        'user_login':'obs_res_count'},
                         inplace=True)
    stat.fillna(0,inplace=True)                                                         #заполняем нулями значения NaN (для тех у кого нет ни одного research)
    stat['obs_res_count'] = stat['obs_res_count'].astype('Int64')                       #меняем "х.0" на "x"
    stat.sort_values(by=['obs_count','obs_res_count','user'],ascending=False,inplace=True)
    stat.insert(1,'position','')
    stat.insert(2,'pos_cool','')
    stat['position'] = range(1,counts.shape[0]+1)                                       #создаём колонку с позицией, взяв кол-во пользователей из shape
    stat['pos_cool'] = stat[['obs_count','obs_res_count']].ne(stat[['obs_count','obs_res_count']].shift()).any(axis=1).cumsum()
    
    return stat


def shiftpos(shiftrow):
    
    if shiftrow['position_y'] == 0:
        cell = '+new'
    elif shiftrow['pos_cool_shift'] > 0:
        cell = '+' + str(shiftrow['pos_cool'])
    else: cell = ''

    return cell

def shiftplus(shift):

    cell = ('+' + str(shift)) if shift > 0 else ''

    return cell


def prepare_changes(df, start_date, finish_date):
    
    
    start_obs = prepare_to_date(df, start_date)
    finish_obs = prepare_to_date(df, finish_date)
    stat = finish_obs.merge(right=start_obs,how='left',left_on='user', right_on='user')   
    stat_changes = pd.DataFrame()
    stat_changes['position'] = stat['position_x']
    stat_changes['position_y'] = stat['position_y']
    stat_changes['pos_cool'] = stat['pos_cool_x']
    stat_changes['pos_cool_shift'] = stat['pos_cool_y'] - stat['pos_cool_x']
    stat_changes['user'] = stat['user']
    stat_changes['obs_count'] = stat['obs_count_x']
    stat_changes['obs_count_shift'] = stat['obs_count_x'] - stat['obs_count_y']
    stat_changes['obs_res_count'] = stat['obs_res_count_x']
    stat_changes['obs_res_count_shift'] = stat['obs_res_count_x'] - stat['obs_res_count_y'] 
    stat_changes.fillna(0,inplace=True)  
    stat_changes['pos_cool_shift'] = stat_changes['pos_cool_shift'].astype('Int64')                       #меняем "х.0" на "x"    
    stat_changes['obs_count_shift'] = stat_changes['obs_count_shift'].astype('Int64')                       #меняем "х.0" на "x"     
    stat_changes['obs_res_count_shift'] = stat_changes['obs_res_count_shift'].astype('Int64')                       #меняем "х.0" на "x"     
    stat_changes['pos_cool_shift'] = stat_changes.apply(shiftpos,axis=1)
    stat_changes['obs_count_shift'] = stat_changes['obs_count_shift'].apply(shiftplus)
    stat_changes['obs_res_count_shift'] = stat_changes['obs_res_count_shift'].apply(shiftplus)
    stat_changes.sort_values(by=['obs_count','obs_res_count','user'],ascending=False,inplace=True)

    return stat_changes


def changes_beauty(changes):

    changes = changes[((changes['pos_cool'] == 11).cumsum() != 1)].copy()
    changes['pos_cool'] = changes['pos_cool'].astype(str) + changes['pos_cool_shift']
    changes['obs_count'] = changes['obs_count'].astype(str) + changes['obs_count_shift']
    changes['obs_res_count'] = changes['obs_res_count'].astype(str) + changes['obs_res_count_shift']
    changes.drop(['position','position_y','pos_cool_shift','obs_res_count_shift','obs_count_shift'], axis=1, inplace=True)
    changes.columns = ['#','Кто','Наблюдения','Наблюдения,<br>    исследовательский уровень']
    
    return changes


def changes_html(changes, htmlname):
  
  changes.to_html(htmlname, header=True, index=False, escape=False, justify='center', border=None)

  with open(htmlname, 'r') as file :
    filedata = file.read()

  filedata = filedata.replace(' class="dataframe"', '') # Replace the target string
  filedata = filedata.replace('<th>', '<th  style="vertical-align:top">')
  filedata = filedata.replace('+new', '<b style="font-size:62%;color:green">&nbsp;&nbsp;NEW</b>')
  filedata = re.sub('\+([0-9]+)',r'<b style="font-size:62%;color:green">&nbsp;&nbsp;&#8593;\1</b>',filedata)

  with open(htmlname, 'w') as file: # Write the file out again
    file.write(filedata)


obs, start_date, finish_date = prepare_df(observations_path, start_date, finish_date)
changes = prepare_changes(obs, start_date, finish_date)
changes = changes_beauty(changes)
changes_html(changes, htmlname)
print('Start date:', start_date)
print('Finish date:', finish_date)
print('Exported to', htmlname)