import os
import pandas as pd
from datetime import date
import re

print('entered to inat_changes.py')


def prepare_df(observations_path, start_date, finish_date):
    df_full = pd.read_csv(observations_path)  # создаём новый огромный датафрейм из csv
    df = df_full[
        [
            'id',
            'user_login',
            'created_at',
            'quality_grade',
            'scientific_name',
            'common_name',
        ]
    ].copy()  # создаём новый маленький датафрейм с нужными столбцами
    del df_full
    df['created_at'] = pd.to_datetime(
        df['created_at'], utc=True
    ).dt.date  # конвертируем столбец с датами наблюдений в тип datatime
    start_date = min(df['created_at']) if start_date == 'min' else start_date
    finish_date = max(df['created_at']) if finish_date == 'max' else finish_date

    return df, start_date, finish_date


def prepare_to_date(df, date_to):
    # prepare_to_date нужна чтобы создать список "лучших"
    # наблюдателей с большим количеством наблюдений на определённую дату

    stat = pd.DataFrame()  # создаём новый датафрейм
    counts = (
        df[df['created_at'] <= date_to].loc[:, 'user_login'].value_counts()
    )  # подсчитываем количество всех наблюдений у каждого пользователя с датой предшествующей или равной date_to
    stat['user'] = counts.index  # создаём колонку с именами пользователей
    stat['obs_count'] = counts.to_list()  # создаём колонку с кол-вом всех наблюдений
    research = (
        df[(df['quality_grade'] == 'research') & (df['created_at'] <= date_to)]
        .loc[:, 'user_login']
        .value_counts()
    )  # подсчитываем кол-во наблюдений со статусом research у каждого пользователя
    del df
    stat = stat.join(
        research, on='user', how='left'
    )  # создаём колонку с кол-вом наблюдений research, объединяя список всех наблюдений со списком наблюдений research
    del research
    stat.rename(
        columns={
            'user': 'user',  # просто нужно переименовать один столбец из-за особенности join
            'obs_count': 'obs_count',
            'user_login': 'obs_res_count',
        },
        inplace=True,
    )
    stat.fillna(
        0, inplace=True
    )  # заполняем нулями значения NaN (для тех у кого нет ни одного research)
    stat['obs_res_count'] = stat['obs_count'].astype('Int64')  # меняем "х.0" на "x"
    stat.sort_values(
        by=['obs_count', 'obs_res_count', 'user'], ascending=False, inplace=True
    )
    stat.insert(1, 'position', '')
    stat.insert(2, 'pos_cool', '')
    stat['position'] = range(
        1, counts.shape[0] + 1
    )  # создаём колонку с позицией, взяв кол-во пользователей из shape
    stat['pos_cool'] = (
        stat[['obs_count', 'obs_res_count']]
        .ne(stat[['obs_count', 'obs_res_count']].shift())
        .any(axis=1)
        .cumsum()
    )

    return stat


def shiftpos(shiftrow):
    if shiftrow['position_y'] == 0:
        cell = '+new'
    elif shiftrow['pos_cool_shift'] > 0:
        cell = '+' + str(shiftrow['pos_cool_shift'])
    else:
        cell = ''

    return cell


def shiftplus(shift):
    cell = ('+' + str(shift)) if shift > 0 else ''

    return cell


def prepare_changes(df, start_date, finish_date):
    start_obs = prepare_to_date(df, start_date)
    finish_obs = prepare_to_date(df, finish_date)
    stat = finish_obs.merge(
        right=start_obs, how='left', left_on='user', right_on='user'
    )
    stat_changes = pd.DataFrame()
    stat_changes['position'] = stat['position_x']
    stat_changes['position_y'] = stat['position_y']
    stat_changes['pos_cool'] = stat['pos_cool_x']
    stat_changes['pos_cool_shift'] = stat['pos_cool_y'] - stat['pos_cool_x']
    stat_changes['user'] = stat['user']
    stat_changes['obs_count'] = stat['obs_count_x']
    stat_changes['obs_count_shift'] = stat['obs_count_x'] - stat['obs_count_y']
    stat_changes['obs_res_count'] = stat['obs_res_count_x']
    stat_changes['obs_res_count_shift'] = (
        stat['obs_res_count_x'] - stat['obs_res_count_y']
    )
    stat_changes.fillna(0, inplace=True)
    stat_changes['pos_cool_shift'] = stat_changes['pos_cool_shift'].astype(
        'Int64'
    )  # меняем "х.0" на "x"
    stat_changes['obs_count_shift'] = stat_changes['obs_count_shift'].astype(
        'Int64'
    )  # меняем "х.0" на "x"
    stat_changes['obs_res_count_shift'] = stat_changes['obs_res_count_shift'].astype(
        'Int64'
    )  # меняем "х.0" на "x"
    stat_changes['pos_cool_shift'] = stat_changes.apply(shiftpos, axis=1)
    stat_changes['obs_count_shift'] = stat_changes['obs_count_shift'].apply(shiftplus)
    stat_changes['obs_res_count_shift'] = stat_changes['obs_res_count_shift'].apply(
        shiftplus
    )

    last_obs = df.groupby(by='user_login')['created_at'].max()
    last_obs.name = 'last_obs'
    stat_changes = stat_changes.merge(right=last_obs, left_on='user', right_index=True)

    stat_changes.sort_values(
        by=['obs_count', 'obs_res_count', 'last_obs', 'user'],
        ascending=False,
        inplace=True,
    )

    return stat_changes


def changes_linking(row, start_date, finish_date, project_id):
    user_id = row['user']

    obs_count = row['obs_count']
    obs_count_shift = row['obs_count_shift']
    obs_res_count = row['obs_res_count']
    obs_res_count_shift = row['obs_res_count_shift']
    pos_cool = row['pos_cool']

    row[
        'obs_count'
    ] = f'<a href="https://www.inaturalist.org/observations?created_d2={finish_date}&place_id=any&project_id={project_id}&subview=map&user_id={user_id}&verifiable=True" style="color:black">{obs_count}</a>&nbsp;&nbsp;'
    row[
        'obs_count_shift'
    ] = f'<a href="https://www.inaturalist.org/observations?created_d1={start_date}&created_d2={finish_date}&place_id=any&project_id={project_id}&subview=map&user_id={user_id}&verifiable=True" style="color:black">{obs_count_shift}</a>'
    row[
        'obs_res_count'
    ] = f'<a href="https://www.inaturalist.org/observations?created_d2={finish_date}&place_id=any&project_id={project_id}&subview=map&user_id={user_id}&verifiable=True&quality_grade=research" style="color:black">{obs_res_count}</a>&nbsp;&nbsp;'
    row[
        'obs_res_count_shift'
    ] = f'<a href="https://www.inaturalist.org/observations?created_d1={start_date}&created_d2={finish_date}&place_id=any&project_id={project_id}&subview=map&user_id={user_id}&verifiable=True&quality_grade=research" style="color:black">{obs_res_count_shift}</a>&nbsp;&nbsp;'

    row['user'] = f'<span color:black">@{user_id}</span>'
    # row['pos_cool'] = f'&nbsp;{pos_cool}'

    return row


def changes_beauty(changes, show_positions):
    if show_positions == 'all':
        show_positions = changes.shape[0] - 1
    changes = changes[
        ((changes['pos_cool'] == (show_positions + 1)).cumsum() != 1)
    ].copy()
    changes['pos_cool'] = changes['pos_cool'].astype(str) + changes['pos_cool_shift']
    changes['obs_count'] = changes['obs_count'].astype(str) + changes['obs_count_shift']
    changes['obs_res_count'] = (
        changes['obs_res_count'].astype(str) + changes['obs_res_count_shift']
    )
    changes.drop(
        [
            'position',
            'position_y',
            'pos_cool_shift',
            'obs_res_count_shift',
            'obs_count_shift',
        ],
        axis=1,
        inplace=True,
    )
    changes['last_obs'] = changes['last_obs'].apply(format_last_obs)
    changes.columns = [
        '#',
        'Кто',
        'Наблюдения',
        'Наблюдения,<br>    исследовательский уровень',
        'Последнее наблюдение',
    ]

    return changes


def format_last_obs(last_obs):
    year, month, day = str(last_obs).split('-')

    spring = range(3, 6)
    summer = range(6, 9)
    autumn = range(9, 12)

    month = int(month)

    if month in spring:
        season = 'весна'
    elif month in summer:
        season = 'лето'
    elif month in autumn:
        season = 'осень'
    else:
        season = 'зима'

    last_obs = season + "'" + year[-2:]

    return last_obs


def changes_html(changes):
    changes.to_html(
        'changes.html',
        header=True,
        index=False,
        escape=False,
        justify='left',
        border=None,
    )

    with open('changes.html', 'r') as file:
        filedata = file.read()

    filedata = filedata.replace(' class="dataframe"', '')  # Replace the target string
    filedata = filedata.replace('<th>', '<th  style="vertical-align:top">')
    filedata = filedata.replace(
        '+new', '&nbsp;<b style="font-size:62%;color:green">NEW</b>'
    )
    filedata = re.sub(
        '\+([0-9]+)', r'<b style="font-size:62%;color:green">&#8593;\1</b>', filedata
    )

    with open('changes.html', 'w') as file:  # Write the file out again
        file.write(filedata)


def main(filename_csv):
    print('entered to main() in inat_changes.py')
    PATH_CSV_BASE = '.'
    start_date = date(2023, 2, 28)
    # start_date = 'min'
    finish_date = date(2023, 8, 31)
    # finish_date = 'max'
    # show_positions = 20
    show_positions = 'all'
    project_id = 'tsyurupy-i-ego-lesa'
    obs, start_date, finish_date = prepare_df(
        os.path.join(PATH_CSV_BASE, filename_csv), start_date, finish_date
    )
    print(start_date, finish_date)
    changes = prepare_changes(obs, start_date, finish_date)
    changes_linked = changes.apply(
        changes_linking,
        axis=1,
        start_date=start_date,
        finish_date=finish_date,
        project_id=project_id,
    )
    changes = changes_beauty(changes_linked, show_positions)
    changes_html(changes)
