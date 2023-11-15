import streamlit as st
import os
import numpy as np
import pandas as pd
import csv
import json
import sys
import toml
from pathlib import Path

st.set_page_config(layout="wide")
st.title("CMD DB")
st.markdown(
    """
<style>
button:not([title="View fullscreen"]) {
    height: auto;
    width: 100% !important;
}
</style>
""",
    unsafe_allow_html=True,
)

dict_index = {}
dict_index["BCT"] = {
    "num_start_line": 3,
    0: "Comment",
    1: "Name",
    2: "ShortName",
    3: "BCID",
    4: "Alias Deploy",
    5: "Alias SetBlockPosition",
    6: "Alias Clear",
    7: "Alias Activate",
    8: "Alias Inactivate",
    9: "Danger Flag",
    10: "Description",
    11: "Note",
}
dict_index["CMD_DB"] = {
    "num_start_line": 4,
    0: "Comment",
    1: "Name",
    2: "Target",
    3: "Code",
    4: "Num Params",
    5: "Param1 Type",
    6: "Param1 Description",
    7: "Param2 Type",
    8: "Param2 Description",
    9: "Param3 Type",
    10: "Param3 Description",
    11: "Param4 Type",
    12: "Param4 Description",
    13: "Param5 Type",
    14: "Param5 Description",
    15: "Param6 Type",
    16: "Param6 Description",
    17: "Danger Flag",
    18: "Is Restricted",
    19: "Description",
    20: "Note",
}


def find_settings_file():
    for parent in [Path(__file__).parents[i] for i in range(4)]:
        for file_name in ["tlm_cmd_db_editor_config.toml", "settings.toml"]:
            path = parent / file_name
            if path.is_file():
                return path
    raise FileNotFoundError("settings.toml / tlm_cmd_db_editor_config.toml is not found.")


# @st.cache_data
def load_settings():
    settings_file = find_settings_file()
    settings = json.loads(json.dumps(toml.load(settings_file)))
    return settings_file.parent, settings


@st.cache_data
def process_csv_files(settings: dict):
    data = {"CMD_DB": {}, "BCT": {}}
    with open(settings["path_cmd_db"], "r", errors="ignore") as csv_file:
        data["CMD_DB"]["path"] = settings["path_cmd_db"]
        rows = list(csv.reader(csv_file, delimiter=","))
        data["CMD_DB"]["Component"] = rows[1][0]
        data["CMD_DB"]["init_rows"] = rows[:dict_index["CMD_DB"]["num_start_line"]]
        rows = rows[dict_index["CMD_DB"]["num_start_line"]:]
        df = pd.DataFrame([{dict_index["CMD_DB"][i]: col for i, col in enumerate(row) if i in dict_index["CMD_DB"]}
                          for row in rows])
        for _type in ["Param1 Type", "Param2 Type", "Param3 Type", "Param4 Type", "Param5 Type", "Param6 Type"]:
            df[_type] = df[_type].astype(
                pd.CategoricalDtype(["", "int8_t", "int16_t", "int32_t", "uint8_t",
                                     "uint16_t", "uint32_t", "float", "double", "raw"]))
        df["Num Params"] = df["Num Params"].astype(pd.CategoricalDtype(["", "0", "1", "2", "3", "4", "5", "6"]))
        df["Danger Flag"] = df["Danger Flag"].astype(pd.CategoricalDtype(["", "danger"]))
        df["Is Restricted"] = df["Is Restricted"].astype(pd.CategoricalDtype(["", "restricted"]))

        data["CMD_DB"]["data"] = df

    with open(settings["path_bct"], "r", errors="ignore") as csv_file:
        data["BCT"]["path"] = settings["path_bct"]
        rows = list(csv.reader(csv_file, delimiter=","))
        data["BCT"]["init_rows"] = rows[:dict_index["BCT"]["num_start_line"]]
        rows = rows[dict_index["BCT"]["num_start_line"]:]
        df = pd.DataFrame([{dict_index["BCT"][i]: col for i, col in enumerate(row) if i in dict_index["BCT"]}
                          for row in rows])
        df["Danger Flag"] = df["Danger Flag"].astype(pd.CategoricalDtype(["", "danger"]))
        data["BCT"]["data"] = df
    return data


@st.cache_data
def calc_bct(df):
    return df


@st.cache_data
def calc_cmd_db(allocation, df):
    allocation = {k.upper(): v for k, v in allocation.items()}
    for index, row in df.iterrows():
        if row['Target'] != '':
            num_params = sum(1 for i in range(1, 7) if row[f'Param{i} Type'] not in ["", None, np.nan])
            df.at[index, 'Num Params'] = str(num_params)
        for _type in ["Param1 Type", "Param2 Type", "Param3 Type", "Param4 Type", "Param5 Type", "Param6 Type"]:
            df[_type].fillna("", inplace=True)

    code_count = 0
    code_count_next = 0
    for index, row in df.iterrows():
        if row['Comment'] == '' and row['Name'] != '':
            code_str = format(code_count, '04X')  # 16進数の書式 '0000'
            df.at[index, 'Code'] = f"0x{code_str}"
            code_count += 1
        elif row['Comment'].startswith('* '):
            word = row['Comment'][2:].upper()
            code_count = code_count_next
            if word in allocation:
                code_count_next += allocation[word]
            else:
                if word != "NONORDER":
                    st.error(f"'{word}' not found in settings.")
    return df


def save(data):
    data_to_write = data["init_rows"]
    data_to_write.extend(data["data"].values.tolist())
    with open(data["path"], mode="w") as csv_file:
        for row in data_to_write:
            csv_file.write(",".join(map(str, row)) + "\n")


path_base, settings = load_settings()
sections = list(settings.keys())
sections = [key for key in sections if "cmddb" in settings[key]]
selected_project = None
if "selected_project" not in st.session_state:
    st.session_state.selected_project = None

if len(sys.argv) > 1 and sys.argv[1] in sections:
    st.session_state.selected_project = sys.argv[1]
    selected_project = st.session_state.selected_project
elif len(sections) == 1:
    st.session_state.selected_project = sections[0]
    selected_project = st.session_state.selected_project
elif st.session_state.selected_project:
    selected_project = st.session_state.selected_project
else:
    selected_project = st.selectbox("Select a project:", sections)
    if st.button("Select"):
        st.session_state.selected_project = selected_project
        st.experimental_rerun()
    st.stop()

settings = settings[selected_project]["cmddb"]
for path_name in ["path_bct", "path_cmd_db"]:
    settings[path_name] = path_base / settings[path_name]

data = process_csv_files(settings)

option = st.selectbox("CMD TYPE", ["CMD_DB", "BCT"])

if option:
    col1, col2 = st.columns(2)
    if option == "BCT":
        data[option]["data"] = calc_bct(data[option]["data"])
        edited_df = st.data_editor(
            data[option]["data"],
            column_config={
                "Code": st.column_config.Column(width="small"),
                "Target": st.column_config.Column(width="small"),
                "Comment": st.column_config.Column(width="small"),
                "Num Params": st.column_config.Column(width="small"),
                "Param1 Type": st.column_config.Column(width="small"),
                "Param2 Type": st.column_config.Column(width="small"),
                "Param3 Type": st.column_config.Column(width="small"),
                "Param4 Type": st.column_config.Column(width="small"),
                "Param5 Type": st.column_config.Column(width="small"),
                "Param6 Type": st.column_config.Column(width="small"),
                "Danger Flag": st.column_config.Column(width="small"),
                "Is Restricted": st.column_config.Column(width="small"),
            },
            width=1600,
            height=1000,
            hide_index=False,
            num_rows="dynamic"
        )
        if col1.button("Save"):
            st.cache_data.clear()
            save(data[option])
            st.experimental_rerun()

        if col2.button("Edit on CSV Editor"):
            os.system("open " + str(data[option]["path"]))
    if option == "CMD_DB":
        edited_df = st.data_editor(
            data[option]["data"],
            column_config={
                "BCID": st.column_config.Column(width="small"),
                "ShortName": st.column_config.Column(width="small"),
                "Alias Deploy": st.column_config.Column(width="small"),
                "Alias SetBlockPosition": st.column_config.Column(width="small"),
                "Alias Clear": st.column_config.Column(width="small"),
                "Alias Activate": st.column_config.Column(width="small"),
                "Alias Inactivate": st.column_config.Column(width="small"),
                "Danger Flag": st.column_config.Column(width="small"),
            },
            width=1600,
            height=1000,
            hide_index=False,
            num_rows="dynamic"
        )
        if col1.button("Save"):
            st.cache_data.clear()
            save(data[option])
            st.experimental_rerun()

        if col2.button("Edit on CSV Editor"):
            os.system("open " + str(data[option]["path"]))
