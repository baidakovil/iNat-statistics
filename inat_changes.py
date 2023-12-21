"""This file contain all functions to obtain html-user-statistics from csv file."""
import logging
import os
import re
import sys
from datetime import date
from typing import Tuple, Union

import pandas as pd
from pandas import DataFrame, Series

logger = logging.getLogger('A.ina')
logger.setLevel(logging.DEBUG)


logger.info('Run inat_changes.py')


def prepare_df(
    observations_path: str,
    start_date: Union[str, date],
    finish_date: Union[str, date],
) -> Tuple[DataFrame, date, date]:
    """
    Read csv, deletes unnecessary data, prepare dates.
    Args:
        observations_path: path to csv file
        start_date: either 'min' or first date
        finish_date: either 'max' or second date
    Returns:
        dataframe to work, first date, second date
    """
    df_full = pd.read_csv(observations_path)
    df = df_full[
        [
            'id',
            'user_login',
            'created_at',
            'quality_grade',
            'scientific_name',
            'common_name',
        ]
    ].copy()
    del df_full
    df['created_at'] = pd.to_datetime(df['created_at'], utc=True).dt.date
    start_date = min(df['created_at']) if start_date == 'min' else start_date
    finish_date = max(df['created_at']) if finish_date == 'max' else finish_date
    if not isinstance(start_date, date) or not isinstance(finish_date, date):
        logger.exception('Can not parse date from file! Exit')
        sys.exit()
    logger.info(start_date, finish_date)
    return df, start_date, finish_date


def prepare_to_date(df: DataFrame, date_to: date) -> DataFrame:
    """
    Prepares 'top-chart' of observers for specific date.
    Args:
        df: dataframe
        date_to: date to prepare top-chart
    Returns:
        Dataframe with sorted users and
    """
    #  Создаём новый датафрейм.
    stat = pd.DataFrame()
    #  Подсчитываем количество всех наблюдений у каждого пользователя с датой
    #  предшествующей или равной date_to.
    counts = df[df['created_at'] <= date_to].loc[:, 'user_login'].value_counts()
    #  Создаём колонку с именами пользователей.
    stat['user'] = counts.index
    #  Создаём колонку с кол-вом всех наблюдений.
    stat['obs_count'] = counts.to_list()
    #  Подсчитываем кол-во наблюдений со статусом research у каждого пользователя.
    research = (
        df[(df['quality_grade'] == 'research') & (df['created_at'] <= date_to)]
        .loc[:, 'user_login']
        .value_counts()
    )
    del df
    #  Создаём колонку с кол-вом наблюдений research, объединяя список всех наблюдений
    #  со списком наблюдений research.
    stat = stat.join(research, on='user', how='left')
    del research
    #  Просто нужно переименовать один столбец из-за особенности join.
    stat.rename(
        columns={
            'user': 'user',
            'obs_count': 'obs_count',
            'user_login': 'obs_res_count',
        },
        inplace=True,
    )
    #  Заполняем нулями значения NaN (для тех у кого нет ни одного research).
    stat.fillna(0, inplace=True)
    #  Меняем "х.0" на "x".
    stat['obs_res_count'] = stat['obs_count'].astype('Int64')
    stat.sort_values(
        by=['obs_count', 'obs_res_count', 'user'], ascending=False, inplace=True
    )
    stat.insert(1, 'position', '')
    stat.insert(2, 'pos_cool', '')
    #  Создаём колонку с позицией, взяв кол-во пользователей из shape.
    stat['position'] = range(1, counts.shape[0] + 1)
    #  Создаём колонку с позицией, учитывая возможно одинаковое кол-во наблюдений.
    stat['pos_cool'] = (
        stat[['obs_count', 'obs_res_count']]
        .ne(stat[['obs_count', 'obs_res_count']].shift())
        .any(axis=1)
        .cumsum()
    )
    return stat


def shiftpos(shiftrow: Series) -> str:
    """
    Add symbol '+' to table to declare that user shifted in table up. If user have no
    observations before, it add symbol '+new', that mean this is new user. Further '+'
    and '+new' will be replaced with html tags.
    Args:
        shiftrow: row with user data
    Returns:
        '+' or '+new' or '': new obs, new user, no new obs
    """
    if shiftrow['position_y'] == 0:
        cell = '+new'
    elif shiftrow['pos_cool_shift'] > 0:
        cell = '+' + str(shiftrow['pos_cool_shift'])
    else:
        cell = ''

    return cell


def shiftplus(shift: int) -> str:
    """
    Add sign '+' to declare user have new observation, same as shiftpos().
    Args:
        shift: new observation quantity
    Returns:
        '+' or ''. Further will be replaced.

    """
    cell = ('+' + str(shift)) if shift > 0 else ''
    return cell


def prepare_changes(
    df_input: DataFrame, start_date: date, finish_date: date, project_id: str
) -> DataFrame:
    """
    Calculate what changes between two dates and sort users on this results.
    Args:
        df_input: origin DataFrame
        start_date: first date
        finish_date: second date
    Returns:
        dataframe with calculated data and sorted users
    """
    #  Определяем положение дел на начальную и конечную дату.
    start_obs = prepare_to_date(df_input, start_date)
    finish_obs = prepare_to_date(df_input, finish_date)
    #  Объединяем и работаем с объединённым датасетом.
    stat = finish_obs.merge(
        right=start_obs, how='left', left_on='user', right_on='user'
    )
    df_stat = pd.DataFrame()
    df_stat['position'] = stat['position_x']
    df_stat['position_y'] = stat['position_y']
    df_stat['pos_cool'] = stat['pos_cool_x']
    df_stat['pos_cool_shift'] = stat['pos_cool_y'] - stat['pos_cool_x']
    df_stat['user'] = stat['user']
    df_stat['obs_count'] = stat['obs_count_x']
    df_stat['obs_count_shift'] = stat['obs_count_x'] - stat['obs_count_y']
    df_stat['obs_res_count'] = stat['obs_res_count_x']
    df_stat['obs_res_count_shift'] = stat['obs_res_count_x'] - stat['obs_res_count_y']
    df_stat.fillna(0, inplace=True)
    #  Меняем "х.0" на "x".
    df_stat['pos_cool_shift'] = df_stat['pos_cool_shift'].astype('Int64')
    df_stat['obs_count_shift'] = df_stat['obs_count_shift'].astype('Int64')
    df_stat['obs_res_count_shift'] = df_stat['obs_res_count_shift'].astype('Int64')
    #  Отмечаем новых пользователей, новые наблюдения, сдвиги вверх по таблице.
    df_stat['pos_cool_shift'] = df_stat.apply(shiftpos, axis=1)
    df_stat['obs_count_shift'] = df_stat['obs_count_shift'].apply(shiftplus)
    df_stat['obs_res_count_shift'] = df_stat['obs_res_count_shift'].apply(shiftplus)
    #  Создаём столбец с датой последнего наблюдения для каждого пользователя.
    last_obs = df_input.groupby(by='user_login')['created_at'].max()
    last_obs.name = 'last_obs'
    df_stat = df_stat.merge(right=last_obs, left_on='user', right_index=True)
    #  Сортируем по своему усмотрению.
    df_stat.sort_values(
        by=['obs_count', 'obs_res_count', 'last_obs', 'user'],
        ascending=False,
        inplace=True,
    )
    if project_id:
        df_stat = df_stat.apply(
            changes_linking,
            axis=1,
            start_date=start_date,
            finish_date=finish_date,
            project_id=project_id,
        )
    return df_stat


def changes_linking(
    row: Series, start_date: date, finish_date: date, project_id: str
) -> Series:
    """
    Add links to observations where and when it possible: if 'project_id' provided.
    Args:
        row: row ot final table
        start_date: first date
        finish_date: secod_date
        project_id: project_id (you can see it in URL)
    Returns:
        row with links
    """
    user_id = row['user']
    obs_count = row['obs_count']
    obs_count_shift = row['obs_count_shift']
    obs_res_count = row['obs_res_count']
    obs_res_count_shift = row['obs_res_count_shift']

    row[
        'obs_count'
    ] = f'<a href="https://www.inaturalist.org/observations?created_d2={finish_date}&\
place_id=any&project_id={project_id}&subview=map&user_id={user_id}&\
verifiable=True" style="color:black">{obs_count}</a>&nbsp;&nbsp;'

    row[
        'obs_count_shift'
    ] = f'<a href="https://www.inaturalist.org/observations?created_d1={start_date}\
&created_d2={finish_date}&place_id=any&project_id={project_id}&subview=map&\
user_id={user_id}&verifiable=True" style="color:black">{obs_count_shift}</a>'

    row[
        'obs_res_count'
    ] = f'<a href="https://www.inaturalist.org/observations?created_d2={finish_date}&\
place_id=any&project_id={project_id}&subview=map&user_id={user_id}&verifiable=True&\
quality_grade=research" style="color:black">{obs_res_count}</a>&nbsp;&nbsp;'

    row[
        'obs_res_count_shift'
    ] = f'<a href="https://www.inaturalist.org/observations?created_d1={start_date}&\
created_d2={finish_date}&place_id=any&project_id={project_id}&subview=map&\
user_id={user_id}&verifiable=True&quality_grade=research" \
style="color:black">{obs_res_count_shift}</a>&nbsp;&nbsp;'

    row['user'] = f'<span color:black">@{user_id}</span>'

    return row


def changes_beauty(changes: DataFrame, show_positions: Union[str, int]) -> DataFrame:
    """
    Add some necessary data for html rendering, that can be added to dataframe.
    Args:
        changes: final dataframe,
        show_positions: how many positions to show in html
    Returns:
        dataframe prepared for converting to html.
    """
    if show_positions == 'all':
        show_positions = changes.shape[0] - 1
    assert isinstance(show_positions, int)
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
    changes.columns = pd.Index(
        data=[
            '#',
            'Кто',
            'Наблюдения',
            'Наблюдения,<br>    исследовательский уровень',
            'Последнее наблюдение',
        ]
    )
    return changes


def format_last_obs(last_obs: date) -> str:
    """
    Format text to column "Last observation date" to human-readable.
    Args:
        last_obs: date of user's last observation
    Returns:
        formatted string
    """
    year, month_str, _ = str(last_obs).split('-')
    spring, summer, autumn = range(3, 6), range(6, 9), range(9, 12)
    month = int(month_str)
    if month in spring:
        season = 'весна'
    elif month in summer:
        season = 'лето'
    elif month in autumn:
        season = 'осень'
    else:
        season = 'зима'
    return season + "'" + year[-2:]


def changes_html(changes: DataFrame) -> None:
    """
    Procedure to save dataframe into html and replace special signs to html code.
    Args:
        changes: dataframe
    """
    changes.to_html(
        'changes.html',
        header=True,
        index=False,
        escape=False,
        justify='left',
        border=None,
    )
    with open('changes.html', 'r', encoding='utf-8') as file:
        filedata = file.read()
    filedata = filedata.replace(' class="dataframe"', '')  # Replace the target string
    filedata = filedata.replace('<th>', '<th  style="vertical-align:top">')
    filedata = filedata.replace(
        '+new', '&nbsp;<b style="font-size:62%;color:green">NEW</b>'
    )
    filedata = re.sub(
        r'\+([0-9]+)', r'<b style="font-size:62%;color:green">&#8593;\1</b>', filedata
    )
    with open('changes.html', 'w', encoding='utf-8') as file:
        file.write(filedata)


def prepare_args(
    input_start: str, input_finish: str, input_pos: str
) -> Tuple[Union[date, str], Union[date, str], Union[int, str]]:
    """
    Function to prepare argument types.
    Args:
        same at in main()
    Returns:
        dates as date if date was passed, otherwise as it was; show_positions as int.
    """
    #  Начальная дата.
    start_prepared: Union[date, str]
    finish_prepared: Union[date, str]
    pos_prepared: Union[int, str]

    if input_start != 'min':
        start_year, start_month, start_day = input_start.split('-')
        start_prepared = date(int(start_year), int(start_month), int(start_day))
    else:
        start_prepared = input_start
    #  Конечная дата.
    if input_finish != 'max':
        finish_year, finish_month, finish_day = input_finish.split('-')
        finish_prepared = date(int(finish_year), int(finish_month), int(finish_day))
    else:
        finish_prepared = input_finish
    #  Количество строк.
    if 'all' not in input_pos:
        pos_prepared = int(input_pos)
    else:
        pos_prepared = input_pos
    return start_prepared, finish_prepared, pos_prepared


def main(
    filename_csv: str,
    input_start: str,
    input_finish: str,
    input_pos: str,
    project_id: str,
) -> None:
    """
    Main function to run all others.
    Args:
        filename_csv: name of the csv to read
        start_date: first date
        finish_date: second date
        show_positions: how many strings to show in the final html table
        project_id: project id to create links to observations
    """
    # tsyurupy-i-ego-lesa
    logger.info('entered to main() in inat_changes.py')
    start, finish, show = prepare_args(input_start, input_finish, input_pos)
    obs, start_dtime, finish_dtime = prepare_df(filename_csv, start, finish)
    changes = prepare_changes(obs, start_dtime, finish_dtime, project_id)
    changes = changes_beauty(changes, show)
    if os.path.exists(filename_csv):
        os.remove(filename_csv)
    changes_html(changes)
