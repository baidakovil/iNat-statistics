"""This file contain all functions to calc html-OBSERVATIONS-statistic from csv file."""
import logging
import re
import sys
import time
from datetime import date
from typing import List, Sequence, Tuple, Union

import numpy as np
import pandas as pd
import requests
from pandas import DataFrame, Series
from requests import HTTPError
from tqdm import tqdm

from services.logger import logger

logger = logging.getLogger('A.ina')
logger.setLevel(logging.DEBUG)

# START_DATE = 'min'
# FINISH_DATE = 'max'
START_DATE = date(2023, 2, 28)
FINISH_DATE = date(2023, 8, 31)
PROJECT_ID = 'tsyurupy-i-ego-lesa'
LAT = '55.494403'
LNG = '38.644662'
PATH_CSV = 'data/observations-390079_tahf_22dec2023.csv'
PATH_DATABASE = 'data/radiuses_dataset.csv'
RADIUSES_LIST = (20, 200, 2000, 0)
SHOW_POS_RARITETS = 20
SHOW_POS_AFRITETS = 15
SEC_SLEEP_TIME = 1
MONTH_NUM = int(FINISH_DATE.strftime('%m'))
MONTHS_RU = {
    1: 'Янв',
    2: 'Фев',
    3: 'Мар',
    4: 'Апр',
    5: 'Май',
    6: 'Июн',
    7: 'Июл',
    8: 'Авг',
    9: 'Сен',
    10: 'Окт',
    11: 'Ноя',
    12: 'Дек',
}
FORMAT_FINISH_DATE = FINISH_DATE.strftime(f'%d {MONTHS_RU.get(MONTH_NUM)} %Y')
RANKS_ENRU = {
    'taxon_kingdom_name': 'Царство',
    'taxon_phylum_name': 'Тип',
    'taxon_subphylum_name': 'Подтип',
    'taxon_superclass_name': 'Надкласс',
    'taxon_class_name': 'Класс',
    'taxon_subclass_name': 'Подкласс',
    'taxon_infraclass_name': 'Инфракласс',
    'taxon_subterclass_name': 'Надкласс',
    'taxon_superorder_name': 'Надотряд',
    'taxon_order_name': 'Отряд',
    'taxon_suborder_name': 'Подотряд',
    'taxon_infraorder_name': 'Инфраотряд',
    'taxon_parvorder_name': 'Парвотряд',
    'taxon_zoosection_name': 'Зоосекция',
    'taxon_zoosubsection_name': 'Зооподсекция',
    'taxon_superfamily_name': 'Надсемейство',
    'taxon_epifamily_name': 'Эписемейство',
    'taxon_family_name': 'Семейство',
    'taxon_subfamily_name': 'Подсемейство',
    'taxon_supertribe_name': 'Надтриба',
    'taxon_tribe_name': 'Триба',
    'taxon_subtribe_name': 'Подтриба',
    'taxon_genus_name': 'Род',
    'taxon_genushybrid_name': 'Genus hybrid',
    'taxon_subgenus_name': 'Подрод',
    'taxon_section_name': 'Секция',
    'taxon_subsection_name': 'Подсекция',
    'taxon_complex_name': 'Комплекс',
    'taxon_species_name': 'Вид',
    'taxon_hybrid_name': 'Гибрид',
    'taxon_subspecies_name': 'Подвид',
    'taxon_variety_name': 'Разновидность',
    'taxon_form_name': 'Форма',
    'taxon_infrahybrid_name': 'Инфрагибрид',
}


def prepare_df(
    csv_path: str, start_date: Union[str, date], finish_date: Union[str, date]
) -> Tuple[DataFrame, date, date]:
    """
    Prepares data to analyze. Read csv, deletes unnecessary, read dates.
    Args:
        observations_path: path to csv
        start_date: either first date of period or 'min'
        finish_date: either second date of period or 'max'
    Returns: cleaned dataframe, first date, second date
    """
    df_full = pd.read_csv(csv_path)
    #  Column reorder.
    df = df_full.loc[:, 'taxon_id':'taxon_form_name'].copy()  # type: ignore
    df.insert(0, 'iconic_taxon_name', df_full['iconic_taxon_name'])
    df.insert(0, 'created_at', '')
    df.insert(0, 'quality_grade', df_full['quality_grade'])
    df.insert(0, 'common_name', df_full['common_name'])
    #  "One-hot encoding."
    df.loc[df['quality_grade'] == 'needs_id', 'quality_grade'] = 0
    df.loc[df['quality_grade'] == 'research', 'quality_grade'] = 1
    #  Type converting.
    df['created_at'] = pd.to_datetime(df_full['created_at']).dt.date
    del df_full
    #  Getting dates.
    if start_date == 'min':
        start_date = min(df['created_at'])
    if finish_date == 'max':
        finish_date = max(df['created_at'])
    if not isinstance(start_date, date) or not isinstance(finish_date, date):
        logger.exception('Can not parse date from file! Exit')
        sys.exit()
    return df, start_date, finish_date


def get_taxons_df_to_date(df: DataFrame, date_to: date) -> DataFrame:
    """
    Creates auxiliary dataframe with data about taxons at current date.
    Args:
        df: origin dataframe after prepare_df()
        date_to: before this date
    Returns:
        taxons info dataframe
    """
    #  Filter to date
    df = df[df['created_at'] <= date_to].copy()
    #  Clear from unnecessary data
    df.drop('created_at', axis=1, inplace=True)
    df.dropna(axis=1, how='all', inplace=True)
    #  Get highest taxons for each observation
    last_levels = df.apply(lambda x: x.last_valid_index(), axis=1)
    levels = df.columns[df.columns.isin(last_levels.unique())].to_list()
    #  Remove intermediate taxon columns for each observation
    df = df[['taxon_id', 'common_name', 'iconic_taxon_name'] + levels].copy()
    #  Create taxons_df dataframe
    taxons_df = DataFrame(
        columns=[
            'taxon_id',
            'taxon_rang',
            'taxon_name',
            'common_name',
            'iconic_taxon_name',
        ]
    )
    for i in range(2, len(df.columns)):
        temp_df = pd.DataFrame()
        level_name = df.columns[i]
        level_filter = df[last_levels == level_name]
        temp_df.insert(loc=0, column='taxon_id', value=level_filter['taxon_id'])
        temp_df.insert(loc=0, column='taxon_rang', value=df.columns[i])
        temp_df.insert(loc=0, column='taxon_name', value=level_filter[level_name])
        temp_df.insert(loc=0, column='common_name', value=level_filter['common_name'])
        temp_df.insert(
            loc=0, column='iconic_taxon_name', value=level_filter['iconic_taxon_name']
        )
        taxons_df = pd.concat([taxons_df, temp_df], axis=0)
    taxons_df.drop_duplicates(inplace=True)
    taxons_df['taxon_id'] = taxons_df['taxon_id'].astype('Int64')
    taxons_df.set_index(keys='taxon_id', drop=True, inplace=True)
    return taxons_df


def update_radius(
    df_taxons: DataFrame, radiuses: Sequence[int], db_path: str, date_to: date
) -> None:
    """
    Procedure to update database with info about how much observations in specific
    radius for specifix taxon. If there is no data in database, fetch from iNaturalist.
    Args:
        df_taxons: dataframe with 'taxon_id' column
        radiuses: list of radiuses
        db_path: db path
        date_to: gather info before this date
    # TODO add center of circles here
    # TODO sql here
    """
    #  Define all data that needed
    csb_col_set = ['taxon_id', 'radius', 'date']
    df_tax_asked = DataFrame(columns=csb_col_set)
    date_str = str(date_to)
    for radius in radiuses:
        df_tax_asked_r = DataFrame()
        df_tax_asked_r['taxon_id'] = df_taxons.index
        df_tax_asked_r.insert(1, 'radius', radius)
        df_tax_asked_r.insert(2, 'date', date_str)
        df_tax_asked = pd.concat([df_tax_asked, df_tax_asked_r])
    df_tax_asked.reset_index(drop=True, inplace=True)
    logger.info('Going to check in csv: %s values', df_tax_asked.shape[0])
    #  Define already loaded data
    df_tax_csv = pd.read_csv(index_col=False, filepath_or_buffer=db_path)
    logger.info('Total in csv: %s values', df_tax_csv.shape[0])
    check_radiuses = pd.merge(
        df_tax_asked, df_tax_csv, how='left', left_on=csb_col_set, right_on=csb_col_set
    )
    already_in_csv_sum = check_radiuses['count'].notnull().sum()
    logger.info('Already in csv: %s values', already_in_csv_sum)
    havenoradiuses = check_radiuses[check_radiuses['count'].isnull()].copy()
    #  Fetch data from iNat.
    if havenoradiuses.shape[0] > 0:
        logger.info('Ask for %s values from iNat', havenoradiuses.shape[0])
        havenoradiuses.drop('count', axis=1, inplace=True)
        fetched = fetch_radius(havenoradiuses)
        fetched_sum = fetched['count'].notnull().sum()
        logger.info('Have fetched %s values from iNat', fetched_sum)
        df_tax_csv = pd.concat([df_tax_csv, fetched])
        df_tax_csv.to_csv(path_or_buf=db_path, index=False)
        del df_tax_csv
    else:
        logger.info('No need to fetch from iNat')
    #  Check "db" "integrity" below
    df_tax_csv = pd.read_csv(index_col=False, filepath_or_buffer=db_path)
    logger.info('Total in csv: %s values ', df_tax_csv.shape[0])
    if not (df_tax_csv.value_counts(subset=csb_col_set) > 1).any():
        logger.info('No duplicates in csv')
    else:
        logger.info('! Somehow duplicates in CSV !')
    check_radiuses = pd.merge(
        df_tax_asked, df_tax_csv, how='left', left_on=csb_col_set, right_on=csb_col_set
    )
    if check_radiuses['count'].notnull().all():
        logger.info(True)
    else:
        logger.info(False)


def fetch_radius(havenoradiuses: DataFrame) -> DataFrame:
    """
    Fetch data from iNaturalist.
    Args:
        havenoradiuses: df with columns 'taxon_id', 'radius', 'date'
    Returns:
        df with columns 'taxon_id', 'radius', 'date', 'count'
    """
    # Create text file for some 'reserve' plain text database for case of fall at load
    current_date = str.replace(str(date.today()), '-', '_')
    current_time = time.strftime('%H_%M_%S', time.localtime())
    temporal_txt_path = 'data/temp_file_' + current_date + '_' + current_time + '.csv'
    with open(file=temporal_txt_path, mode='a', encoding='utf-8') as temp_file:
        temp_file.write('taxon_id,radius,date,count\n')
    df = DataFrame(columns=['taxon_id', 'radius', 'date', 'count'])
    for i in tqdm(range(havenoradiuses.shape[0])):
        assert isinstance(i, int)
        taxon_id = havenoradiuses.iloc[i, 0]
        radius = havenoradiuses.iloc[i, 1]
        date_to = havenoradiuses.iloc[i, 2]
        if radius == 0:
            geoparams = ['', '', '']
        else:
            geoparams = [LAT, LNG, str(radius)]
        params = {
            'verifiable': 'true',
            'taxon_id': str(taxon_id),
            'd2': str(date_to),
            'lat': geoparams[0],
            'lng': geoparams[1],
            'radius': geoparams[2],
            'order': 'desc',
            'order_by': 'created_at',
            'only_id': 'true',
        }
        ##################################
        ##### LINE BELOW LOAD DATA ! #####
        ##################################
        response = requests.get(
            url='https://api.inaturalist.org/v1/observations', params=params, timeout=20
        )
        count = response.json()['total_results']
        df.loc[i] = [taxon_id, radius, date_to, count]  # type: ignore
        #  Write to reserve file.
        with open(temporal_txt_path, 'a', encoding='utf-8') as temp_file:
            db_line = [str(taxon_id), str(radius), str(date_to), str(count)]
            temp_file.write(','.join(db_line) + '\n')
        if response.status_code != 200:
            logger.warning('Response is not 200: %s. Smth wrong', response.status_code)
            raise HTTPError('Oh, response is not 200, it is ', response.status_code)
        time.sleep(SEC_SLEEP_TIME)
        logger.info(
            'Done loop %s: r%s, date %s, response %s, count %s, id %s',
            i,
            radius,
            date_to,
            response.status_code,
            count,
            taxon_id,
        )
    return df


def get_radius(
    taxons_list: DataFrame, date_to: str, taxons_df_finish: DataFrame
) -> DataFrame:
    """
    Reads database for current taxons for specific date.
    Args:
        taxons_list: df with index as taxon list
        date_to: date
        tax_df_finish: df with index as taxons list
    Returns:
        dataframe with counts
    """
    df = pd.DataFrame()
    df_tax_csv = pd.read_csv(index_col='taxon_id', filepath_or_buffer=PATH_DATABASE)
    df.index = taxons_list.index
    df_tax_csv_todate = df_tax_csv[
        (df_tax_csv['date'] == date_to)
        & (df_tax_csv.index.isin(taxons_df_finish.index))
    ]
    df = df.merge(df_tax_csv_todate, how='left', left_index=True, right_index=True)
    return df


def get_cool_indexes(column: Series) -> Series:
    """
    Make chart-list (1, 2, 3, 3, 4, ...) where same numbers are for same vals.
    Args:
        column: column (which one?)
    Returns:
        column with positions
    """
    series_sorted = column.sort_values()
    positions = series_sorted.ne(series_sorted.shift()).cumsum()
    positions = positions.align(column)[0]
    return positions


def get_radius_info(
    taxons_df_start: DataFrame,
    taxons_df_finish: DataFrame,
    df_orig: DataFrame,
) -> DataFrame:
    """
    Main function where prepares almost all info. Takes all the sources: original
    dataframe taxons data, original dataframe, database, dates.
    Args:
        tax_df_start: df with index as taxons at start date, to mark taxons as "new"
        tax_df_finish: df with all the taxons. Need for index, columns, data
        df_orig: original dataframe after prepare_df(), used for count totals of RG obs.
    Returns:
        Multiindexed dataframe with
            1st level -> 2nd level indexes:
            'full_pos' -> no 2nd: simple position in list
            '<finish date>' -> radiuses (4 columns!) at 2nd: counts
            'count_diff' -> radiuses at 2nd: counts delta
            'pos_finish' -> radiuses at 2nd: "cool" position
            'ifnew' -> no 2nd: new taxon or not ('new'/NaN)
            research -> no 2nd: research or not (0/1)
            taxon_rang -> no 2nd: english name for taxon_rang
            taxon_name -> no 2nd: Latin name for taxon
            common_name -> no 2nd: Common name for taxon
            iconic_taxon_name: English iconic taxon name
    """

    df = df_orig[df_orig['created_at'] <= FINISH_DATE].copy()
    start_date_str = str(START_DATE)
    finish_date_str = str(FINISH_DATE)

    #  Get data from csv for all taxons
    df_start = get_radius(taxons_df_finish, start_date_str, taxons_df_finish)
    df_finish = get_radius(taxons_df_finish, finish_date_str, taxons_df_finish)
    df_compact = (
        pd.concat([df_start, df_finish])
        .pivot(columns=['date', 'radius'], values='count')
        .copy()
    )
    #  Calculate difference for two dates
    df_diff_series = (
        df_compact.loc[:, finish_date_str] - df_compact.loc[:, start_date_str]
    )
    df_diff = pd.concat([df_diff_series], keys=['count_diff'], axis=1)
    #  Mark with positions
    df_pos_start = df_compact[
        df_compact[(start_date_str, RADIUSES_LIST[-1])].notnull()
    ][start_date_str].apply(get_cool_indexes, axis=0)
    df_pos_start = pd.concat([df_pos_start], keys=['pos_start'], axis=1)
    df_pos_finish = df_compact[finish_date_str].apply(get_cool_indexes, axis=0)
    df_pos_finish = pd.concat([df_pos_finish], keys=['pos_finish'], axis=1)
    #  Sort dataframe
    sort_list = [('pos_finish', RADIUSES_LIST[i]) for i in range(len(RADIUSES_LIST))]
    df_pos_finish = df_pos_finish.sort_values(by=sort_list)  # type: ignore
    df_pos = pd.concat([df_compact, df_diff, df_pos_start, df_pos_finish], axis=1)
    df_pos = df_pos.reindex(index=df_pos_finish.index)
    df_pos = sort_index(df_pos)
    df_pos = df_pos.astype('Int64')
    df_pos.insert(0, ('full_pos'), range(1, df_pos.shape[0] + 1))
    #  Put marks "NEW" for new taxons
    df_pos.loc[~df_pos.index.isin(taxons_df_start.index), ('ifnew')] = 'new'
    #  Count research grade observations
    df_pos[('research')] = (
        df[['taxon_id', 'quality_grade']].groupby(by='taxon_id', axis=0).sum()
    )
    #  Reformat df
    taxons_df_finish.columns = (  # type: ignore
        ('taxon_rang', ''),
        ('taxon_name', ''),
        ('common_name', ''),
        ('iconic_taxon_name', ''),
    )
    df_pos = pd.concat([df_pos, taxons_df_finish], axis=1)
    df_pos.drop([str(start_date_str), 'pos_start'], axis=1, inplace=True, level=0)
    return df_pos


def sort_index(df: DataFrame) -> DataFrame:
    """
    Sort main multiindex dataframe columns. Needs after some inserts/deletes or ...
    Args:
        df: multiindex dataframe
    Returns:
        df: same df, but sorted
    """
    sort_dict_order = [
        'result_pos',
        'result_name',
        'result_count',
        str(START_DATE),
        str(FINISH_DATE),
        'full_pos',
        'count_diff',
        'pos_start',
        'pos_finish',
        'pos_diff',
        'ifnew',
        'taxon_rang',
        'taxon_name',
        'iconic_taxon_name',
        'common_name',
        'research',
    ] + list(RADIUSES_LIST)
    sort_dict = {sort_dict_order[i]: i for i in range(len(sort_dict_order))}
    df = df.sort_index(axis=1, level=[0, 1], key=lambda x: x.map(sort_dict))
    return df


def formatcount(count: Union[int, str], count_diff: bool = False) -> Union[int, str]:
    """
    Apply human-readable formatting of count numbers. Typing here just a mess, sorry.
    Args:
        count: number of observations
        count_diff: whether should add '+'
    Returns:
        formatted count
    """
    if isinstance(count, int):
        if count > 1000000:
            count = str(round(count / 1000000, 1)) + 'M'
        elif count > 10000:
            count = str(int(count / 1000)) + 'K'
        elif count > 1000:
            count = str(round(count / 1000, 1)) + 'K'
    if count and count_diff:
        count = '+' + str(count)
    elif (not count) and count_diff:
        count = ''
    return count


def addresult_columns(df: DataFrame) -> DataFrame:
    """
    Add radius x 3 new empty columns to main dataframe (after get_radius_info()).
    Args:
        dataframe with full info
    Returns:
        same df with empty columns
    """
    for columnset in ['result_name', 'result_pos', 'result_count']:
        columnset_df = DataFrame(
            columns=pd.MultiIndex.from_product(
                [[columnset], RADIUSES_LIST], names=['date', 'radius']
            ),
            index=df.index,
        )
        columnset_df[columnset][RADIUSES_LIST[0]] = df[str(FINISH_DATE)][
            RADIUSES_LIST[0]
        ]
        df = pd.concat([df, columnset_df], axis=1)
    df = sort_index(df)
    return df


def add_apply_formats(df: DataFrame) -> DataFrame:
    """
    Do translations of taxon rangs and apply human-readable count formats.
    Args:
        main multiindex df
    Returns:
        same formatted df
    """
    df['taxon_rang'] = df['taxon_rang'].apply(RANKS_ENRU.get)
    df[str(FINISH_DATE)] = df[str(FINISH_DATE)].applymap(formatcount)
    df['count_diff'] = df['count_diff'].applymap(formatcount, count_diff=True)
    return df


def joininfo(row: Series) -> Series:
    """
    Basing on values of fields in main table, put valuable info in result columns:
    links, colors, HTML tags, line breaks, formatting, taxon rang names...
    Update columns:
    'result_name', 'result_count', 'research', 'result_pos', 'iconic_taxon_name'.
    Args:
        row: row in main table
    Returns:
        row with final info
    """
    taxon_name = row['taxon_name'].item()
    common_name = row['common_name'].item()
    ifnew = row['ifnew'].item()
    taxon_rang = row['taxon_rang'].item()
    count_diff = row['count_diff'].astype('string')
    count = row[str(FINISH_DATE)].astype('string')
    taxon_id = row.name
    research = row['research'].item()
    iconic_taxon_name = str(row['iconic_taxon_name'].item()).lower()
    taxon_name_link = f'<a href=https://www.inaturalist.org/taxa/{taxon_id} \
style="color:black">{str(taxon_name)}</a>'
    common_name_link = f'<a href=https://www.inaturalist.org/taxa/{taxon_id} \
style="color:black">{str(common_name).title()}</a>'

    if pd.isnull(common_name):
        bold = f'<b>{taxon_name_link}</b>'
        italic = '<br>'
    else:
        bold = f'<b>{common_name_link}</b>'
        italic = f'<br><i>{taxon_name}</i>'

    if pd.isnull(ifnew):
        ifnew = ''
    else:
        ifnew = '<br><b style="font-size:62%;color:green">NEW</b>'

    if not research:
        research = (
            f'<a href=https://www.inaturalist.org/observations?'
            f'&project_id={PROJECT_ID}'
            '&subview=map&nelat=55.526&nelng=38.85&swlat=55.423&swlng=38.536'
            f'&taxon_id={taxon_id} style="color:black">Need ID</a>'
        )
    else:
        research = (
            f'<a href=https://www.inaturalist.org/observations?'
            f'&project_id={PROJECT_ID}'
            '&subview=map&nelat=55.526&nelng=38.85&swlat=55.423&swlng=38.536'
            f'&taxon_id={taxon_id} style="color:green"><b>RG&#xD7;{research}</b></a>'
        )

    if taxon_rang == 'Вид':
        taxon_rang = ''
    else:
        taxon_rang = f' {taxon_rang}'

    row['research'] = research
    row['result_name'] = bold + taxon_rang + italic
    row['result_pos'] = ifnew

    row[
        'iconic_taxon_name'
    ] = f'<img src=https://www.inaturalist.org/assets/iconic_taxa/{iconic_taxon_name}\
-cccccc-20px.png alt={iconic_taxon_name}>'

    row['result_count'] = (
        f'<a href=https://www.inaturalist.org/observations?'
        '&place_id=any'
        f'&lat={LAT}&lng={LNG}&radius=xxx'
        '&subview=table'
        f'&taxon_id={taxon_id} style="color:black">' + count + '</a> ' + count_diff
    )

    return row


def sort_separate(df: DataFrame, raritets_sort: bool) -> List[DataFrame]:
    """
    Separate main dataset into len(radiuses) dataframes and prepares headers.
    Args:
        df: main dataframe with html tags
        raritets_sort: if it table of rarest species or no
    Returns:
        list of dataframes for each of radiuses
    """
    if not raritets_sort:
        afritet_rang = [
            'Вид',
            'Гибрид',
            'Подвид',
            'Разновидность',
            'Форма',
            'Инфрагибрид',
        ]
        df = df[df['taxon_rang'].isin(afritet_rang)]
        show_positions = SHOW_POS_AFRITETS
    else:
        show_positions = SHOW_POS_RARITETS

    radiuse_array = np.asarray(RADIUSES_LIST)
    dataframes = []
    count_col_name: str = ''
    radius_pars = f'&lat={LAT}&lng={LNG}&radius=xxx'

    for radius in RADIUSES_LIST:
        sort_list = [
            ('pos_finish', radiuse_array[i]) for i in range(len(radiuse_array))
        ]

        df = df.sort_values(by=sort_list, ignore_index=True)  # type: ignore

        full_pos_col = 'pos_' + str(radius)
        df.insert(0, full_pos_col, range(1, df.shape[0] + 1))
        df[full_pos_col] = df[full_pos_col].astype('string')

        df = df.sort_values(
            by=sort_list, ignore_index=True, ascending=raritets_sort  # type:ignore
        )

        if radius:
            count_col_name = f'Количество наблюдений<br>в радиусе {radius}\
 км на {FORMAT_FINISH_DATE}'
        else:
            count_col_name = 'Количество наблюдений<br>во всём iNat'
            df.loc[:, ('result_count', radius)] = df['result_count'][radius].apply(
                lambda x: x.replace(radius_pars, ''),
            )

        if raritets_sort:
            taxonname_col_name = 'Название таксона'
        else:
            taxonname_col_name = 'Название вида<br>или подвида'

        df_sorted = pd.DataFrame(
            columns=[
                '#<br>по редкости',
                'Статус<br>в проекте',
                ' ',
                taxonname_col_name,
                count_col_name,
            ]
        )
        df_sorted.iloc[:, 0] = df[full_pos_col] + df['result_pos'][radius]
        df_sorted.iloc[:, 1] = df['research']
        df_sorted.iloc[:, 2] = df['iconic_taxon_name']
        df_sorted.iloc[:, 3] = df['result_name'][radius]
        df_sorted.iloc[:, 4] = df['result_count'][radius]

        df_sorted = df_sorted.iloc[0:show_positions, :]
        dataframes.append(df_sorted)

        radiuse_array = np.roll(radiuse_array, -1)

    return dataframes


def raritets_html(raritets: List[DataFrame], raritets_sort: bool) -> None:
    """
    Write dataframes to files and finally replace some strings with actual values.
    Args:
        raritets: list of dataframes for each of radiuses
        raritets_sort: if it table of rarest species or no
    """
    prefix = 'raritets' if raritets_sort else 'afritets'
    for i, radius in enumerate(RADIUSES_LIST):
        htmlname = f'output/{prefix}_' + str(radius) + '.html'
        df_to_export = raritets[i]
        df_to_export.to_html(
            htmlname,
            header=True,
            index=False,
            escape=False,
            justify='center',
            border=None,
        )

        with open(htmlname, 'r', encoding='utf-8') as file:
            filedata = file.read()

        # Replace the target string
        filedata = filedata.replace(' class="dataframe"', '')
        # Replace the target string
        filedata = filedata.replace('radius=xxx', f'radius={radius}')
        filedata = filedata.replace(
            '<td><b style="color',
            '<td style="vertical-align:top;text-align: center"><b style="color',
        )

        filedata = filedata.replace(
            '<th>#', '<th  style="vertical-align:top" width="10%">#'
        )
        filedata = filedata.replace(
            '<th>Статус в проекте',
            '<th  style="vertical-align:top" width="15%">Статус в проекте',
        )
        filedata = filedata.replace(
            '<th>Статус в проекте', '<th  style="vertical-align:top" width="5%"> '
        )
        filedata = filedata.replace(
            '<th>Название таксона',
            '<th  style="vertical-align:top" width="40%">Название таксона',
        )
        filedata = filedata.replace(
            '<th>Количество наблюдений<br>во всём iNat',
            f'<th  style="vertical-align:top" width="30%">Количество наблюдений<br>\
во всём iNat на {FORMAT_FINISH_DATE}',
        )

        filedata = filedata.replace(
            '+new', '<b style="font-size:62%;color:green">&nbsp;&nbsp;NEW</b>'
        )
        filedata = filedata.replace('<tr>', '<tr height="50px">')
        filedata = filedata.replace(
            '<td><img',
            '<td align="center" style="text-align: center; vertical-align: middle;"><img',
        )
        filedata = re.sub(
            r'\+([0-9]*\.?[0-9]+K?)',
            r'<b style="font-size:62%;color:green">&nbsp;&nbsp;&#8593;\1</b>',
            filedata,
        )
        with open(htmlname, 'w', encoding='utf-8') as file:
            file.write(filedata)


def main(start_date, finish_date):
    """
    Main function to load others
    """
    #  Create dataframe.
    df_taxons, start_date, finish_date = prepare_df(PATH_CSV, start_date, finish_date)
    #  Prepare all the taxon data we have in user's csv.
    tax_df_finish = get_taxons_df_to_date(df_taxons, finish_date)
    tax_df_start = get_taxons_df_to_date(df_taxons, start_date)
    #  Updata database if needed.
    update_radius(
        df_taxons=tax_df_finish,
        radiuses=RADIUSES_LIST,
        db_path=PATH_DATABASE,
        date_to=start_date,
    )
    update_radius(
        df_taxons=tax_df_finish,
        radiuses=RADIUSES_LIST,
        db_path=PATH_DATABASE,
        date_to=finish_date,
    )
    #  Put all the info — database, taxons, dates — into main dataframe and do calculations.
    df_pos = get_radius_info(tax_df_start, tax_df_finish, df_taxons)
    #  Add translation and humand readability
    df_added_formats = add_apply_formats(df_pos)
    #  Insert empty columns.
    df_added_res_cols = addresult_columns(df_added_formats)
    #  Put all the info together to columns basing on apps logic.
    df_info = df_added_res_cols.apply(joininfo, axis=1)
    #  Separate datasets by radiuses
    raritets = sort_separate(df_info, raritets_sort=True)
    afritets = sort_separate(df_info, raritets_sort=False)
    #  Write datasets to files
    raritets_html(raritets, raritets_sort=True)
    raritets_html(afritets, raritets_sort=False)


if __name__ == '__main__':
    main(START_DATE, FINISH_DATE)
