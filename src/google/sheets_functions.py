import pygsheets
import pandas as pd


def open_worksheet(book_name, wks_name):
    gc = pygsheets.authorize()
    sh = gc.open(book_name)
    wks = sh.worksheet_by_title(wks_name)
    return wks


def append_data(init_wks, df_to_append):
    wks = init_wks.get_as_df()
    wks = wks.append(df_to_append, sort=False)
    init_wks.set_dataframe(wks, (1, 1))

    return wks


def remove_data(init_wks, df_to_remove, update):
    wks = init_wks.get_as_df()
    wks['utc_time'] = pd.to_datetime(wks['utc_time'])
    df_to_remove['utc_time'] = pd.to_datetime(df_to_remove['utc_time'])
    wks = wks.merge(df_to_remove, on=list(df_to_remove.columns.values), how='left', indicator=True)
    wks = wks[wks['_merge'] == 'left_only']
    del wks['_merge']
    init_wks.clear()
    init_wks.set_dataframe(wks, (1, 1))

    return wks
