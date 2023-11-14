import csv
import os
import sys
import typing
from pathlib import Path

import pandas as pd
import streamlit as st
import toml

st.set_page_config(layout="wide")
st.title("TLM DB")

# グローバル変数の定義
dict_index = {
    0: "Comment",
    1: "Name",
    2: "VarType",
    3: "VarOrFunc",
    4: "ExtType",
    5: "OctPos",
    6: "BitPos",
    7: "BitLen",
    8: "ConvType",
    9: "a0",
    10: "a1",
    11: "a2",
    12: "a3",
    13: "a4",
    14: "a5",
    15: "ConvInfo",
    16: "Description",
    17: "Note",
}

type2bit = {
    "int8_t": 8,
    "int16_t": 16,
    "int32_t": 32,
    "uint8_t": 8,
    "uint16_t": 16,
    "uint32_t": 32,
    "float": 32,
    "double": 64,
}

num_start_line = 8


@st.cache_data
def load_settings():
    path_base = next(
        (
            p
            for p in [
                Path(__file__).parent,
                Path(__file__).parent.parent,
                Path(__file__).parent.parent.parent,
                Path(__file__).parent.parent.parent.parent,
            ]
            if (p / "tlm_cmd_db_editor_config.toml").is_file()
        ),
        None,
    )
    if path_base is None:
        path_base = next(
            (
                p
                for p in [
                    Path(__file__).parent,
                    Path(__file__).parent.parent,
                    Path(__file__).parent.parent.parent,
                    Path(__file__).parent.parent.parent.parent,
                ]
                if (p / "settings.toml").is_file()
            ),
            None,
        )
    else:
        settings = toml.load(path_base / "tlm_cmd_db_editor_config.toml")
    if path_base is None:
        raise FileNotFoundError("settings.toml / tlm_cmd_db_editor_config.toml is not found.")
    else:
        settings = toml.load(path_base / "settings.toml")
    return path_base, settings


@st.cache_data
def extract_data(csv_path: Path, settings: dict):
    data = {"path": Path(), "name": "", "data": pd.DataFrame()}
    with open(csv_path, "r", errors="ignore") as csv_file:
        data["path"] = csv_path
        data["name"] = csv_path.stem.replace(f'{settings["prefix"]}', "")
        rows = list(csv.reader(csv_file, delimiter=","))
        data.update({rows[i][1]: rows[i][2] for i in range(4)})
        data[rows[0][3]] = rows[1][3]
        rows = rows[num_start_line:]
        df = pd.DataFrame([{dict_index[i]: col for i, col in enumerate(row) if i in dict_index}
                          for row in rows if row[1]])

        bitlen_pre = 0
        bitlen_pre_init = True
        for index, row in df.iterrows():
            index = typing.cast(int, index)
            if row["VarType"] == "||":
                if bitlen_pre_init:
                    df.at[index - 1, "BitLen"] = bitlen_pre
                    bitlen_pre_init = False
            else:
                bitlen_pre, bitlen_pre_init = row["BitLen"], True
                df.at[index, "BitLen"] = type2bit[row["VarType"]]
            if row["ConvType"] == "POLY":
                for i in range(6):
                    if row[f"a{i}"] == "":
                        break
                    df.at[index, "ConvInfo"] += f"a{i}=" + row[f"a{i}"] + ","
                if df.at[index, "ConvInfo"][-1] == ",":
                    df.at[index, "ConvInfo"] = df.at[index, "ConvInfo"][:-1]

        df["VarType"] = df["VarType"].astype(
            pd.CategoricalDtype(["||", "int8_t", "int16_t", "int32_t", "uint8_t",
                                "uint16_t", "uint32_t", "float", "double"])
        )
        df["ExtType"] = df["ExtType"].astype(pd.CategoricalDtype(["PACKET", "TC_FRAME"]))
        df["BitLen"] = df["BitLen"].astype(int)
        df["ConvType"] = df["ConvType"].astype(pd.CategoricalDtype(["NONE", "HEX", "POLY", "STATUS"]))
        df["ConvInfo"] = df["ConvInfo"].str.replace("@@ ", ",").str.replace("@@", ",")
        data["data"] = df
    return data


def make_header(df: pd.DataFrame):
    header = [
        ["", "Target", df.loc[0, "Target"], "Local Var", "",
            "", "", "", "", "", "", "", "", "", "", "", "", ""],
        ["", "PacketID", df.loc[0, "PacketID"], df.loc[0, "Local Var"],
            "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        ["", "Enable/Disable", df.loc[0, "Enable/Disable"], "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        ["", "IsRestricted", df.loc[0, "IsRestricted"], "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        [
            "Comment",
            "TLM Entry",
            "Onboard Software Info.",
            "",
            "Extraction Info.",
            "",
            "",
            "",
            "Conversion Info.",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Description",
            "Note",
        ],
        [
            "",
            "Name",
            "Var.%%##Type",
            "Variable or Function Name",
            "Ext.%%##Type",
            "Pos. Desiginator",
            "",
            "",
            "Conv.%%##Type",
            "Poly (Σa_i * x^i)",
            "",
            "",
            "",
            "",
            "",
            "Status",
            "",
            "",
        ],
        ["", "", "", "", "", "Octet%%##Pos.", "bit%%##Pos.", "bit%%##Len.",
            "", "a0", "a1", "a2", "a3", "a4", "a5", "", "", ""],
    ]
    return header


def export(df: pd.DataFrame, data: dict, settings: dict) -> None:
    save(df, data, settings)
    data_to_write = make_header(df)
    for index, row in data["data"].iterrows():
        if row["VarType"] == "||":
            row["VarType"] = ""
        if row["ConvType"] == "STATUS":
            status = row["ConvInfo"].replace(",", "@@")
            a0, a1, a2, a3, a4, a5 = "", "", "", "", "", ""
        elif row["ConvType"] == "POLY":
            status = ""
            params = row["ConvInfo"].split(",")
            for i in range(6 - len(params)):
                params.append("")
            a0, a1, a2, a3, a4, a5 = [param.split("=")[1] if len(param) > 1 else "" for param in params]
        else:
            status = ""
            a0, a1, a2, a3, a4, a5 = "", "", "", "", "", ""
        data_to_write.append(
            [
                row["Comment"],
                row["Name"],
                row["VarType"],
                row["VarOrFunc"],
                row["ExtType"],
                row["OctPos"],
                row["BitPos"],
                row["BitLen"],
                row["ConvType"],
                a0,
                a1,
                a2,
                a3,
                a4,
                a5,
                status,
                row["Description"],
                row["Note"],
            ]
        )
    with open(settings["dest_path"] / data["path"].name, mode="w") as csv_file:
        for row in data_to_write:
            csv_file.write(",".join(map(str, row)) + "\n")


def save(df: pd.DataFrame, data: dict, settings: dict) -> None:
    data_to_write = make_header(df)
    for index, row in data["data"].iterrows():
        if index == 0:
            data_to_write.append(
                [
                    row["Comment"],
                    row["Name"],
                    row["VarType"],
                    row["VarOrFunc"],
                    row["ExtType"],
                    "0",
                    "0",
                    row["BitLen"],
                    row["ConvType"],
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    row["Description"],
                    row["Note"],
                ]
            )
        else:
            if row["VarType"] == "||":
                bitlen = row["BitLen"]
            elif row["BitLen"] != type2bit[row["VarType"]]:
                bitlen = row["BitLen"]
            else:
                bitlen = """=IF(OR(EXACT(RC[-5]@@"uint8_t")@@EXACT(RC[-5]@@"int8_t"))@@8@@IF(OR(EXACT(RC[-5]@@"uint16_t")@@EXACT(RC[-5]@@"int16_t"))@@16@@IF(OR(EXACT(RC[-5]@@"uint32_t")@@EXACT(RC[-5]@@"int32_t")@@EXACT(RC[-5]@@"float"))@@32@@IF(EXACT(RC[-5]@@"double")@@64))))"""

            if row["ConvType"] == "STATUS":
                status = row["ConvInfo"].replace(",", "@@ ")
                a0, a1, a2, a3, a4, a5 = "", "", "", "", "", ""
            elif row["ConvType"] == "POLY":
                status = ""
                params = row["ConvInfo"].split(",")
                for i in range(6 - len(params)):
                    params.append("")
                a0, a1, a2, a3, a4, a5 = [param.split("=")[1] if len(param) > 1 else "" for param in params]
            else:
                status = ""
                a0, a1, a2, a3, a4, a5 = "", "", "", "", "", ""

            data_to_write.append(
                [
                    row["Comment"],
                    row["Name"],
                    row["VarType"],
                    row["VarOrFunc"],
                    row["ExtType"],
                    "=R[-1]C+INT((R[-1]C[1]+R[-1]C[2])/8)",
                    "=MOD((R[-1]C+R[-1]C[1])@@8)",
                    bitlen,
                    row["ConvType"],
                    a0,
                    a1,
                    a2,
                    a3,
                    a4,
                    a5,
                    status,
                    row["Description"],
                    row["Note"],
                ]
            )
    with open(data["path"], mode="w") as csv_file:
        for row in data_to_write:
            csv_file.write(",".join(map(str, row)) + "\n")


@st.cache_data
def process_csv_files(settings: dict):
    csv_path_list = get_csv_paths(settings)
    return [extract_data(csv_path, settings) for csv_path in csv_path_list]


@st.cache_data
def get_csv_paths(settings: dict):
    db_prefix = settings["prefix"]
    p = Path(settings["path"])
    p_list = list(p.glob("*.csv"))
    if db_prefix is not None:
        p_list = [p for p in p_list if db_prefix in str(p)]
    return p_list


@st.cache_data
def calc_data(df: pd.DataFrame) -> pd.DataFrame:
    cumsum = df["BitLen"].astype(int)[:-1].cumsum().tolist()
    octpos = [_ // 8 for _ in cumsum]
    bitpos = [_ % 8 for _ in cumsum]
    df["OctPos"] = [0] + octpos
    df["BitPos"] = [0] + bitpos
    df = df.reindex(
        columns=["Comment", "Name", "VarType", "VarOrFunc", "ExtType", "OctPos",
                 "BitPos", "BitLen", "ConvType", "ConvInfo", "Description", "Note"]
    )
    return df


# メインアプリケーションの実行


path_base, settings = load_settings()
sections = list(settings.keys())
sections = [key for key in sections if "tlmdb" in settings[key]]
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

settings = settings[selected_project]["tlmdb"]
settings["path"] = path_base / settings["path"]
settings["dest_path"] = path_base / settings["dest_path"]

data = process_csv_files(settings)

option = st.selectbox("TLM NAME", [d["name"] for d in data])

if option:
    selected_data = next(d for d in data if d["name"] == option)

    selected_columns = ["Target", "PacketID", "Enable/Disable", "IsRestricted", "Local Var"]
    df = pd.DataFrame({col: [selected_data.get(col, "")] for col in selected_columns})
    df["Target"] = df["Target"].astype(pd.CategoricalDtype(categories=["OBC"]))
    df["Enable/Disable"] = df["Enable/Disable"].astype(pd.CategoricalDtype(categories=["ENABLE", "DISABLE"]))
    df["IsRestricted"] = df["IsRestricted"].astype(pd.CategoricalDtype(categories=["TRUE", "FALSE"]))

    selected_data["data"] = calc_data(selected_data["data"])
    edited_df = st.data_editor(
        df,
        column_config={
            "Target": st.column_config.Column(width="small"),
            "PacketID": st.column_config.Column(width="small"),
            "Enable/Disable": st.column_config.Column(width="small"),
            "IsRestricted": st.column_config.Column(width="small"),
        },
        width=1600,
        hide_index=True,
    )
    col1, col2, col3, col4 = st.columns(4)
    edited_data = {}
    edited_data["data"] = st.data_editor(
        selected_data["data"],
        num_rows="dynamic",
        column_config={
            "Comment": st.column_config.Column(width="small"),
            "Name": st.column_config.Column(width="medium"),
            "VarType": st.column_config.Column(width="small"),
            "VarOrFunc": st.column_config.Column(width="medium"),
            "ExtType": st.column_config.Column(width="small"),
            "BitLen": st.column_config.Column(width="small"),
            "ConvType": st.column_config.Column(width="small"),
            "ConvInfo": st.column_config.Column(width="medium"),
            "Description": st.column_config.Column(width="medium"),
            "Note": st.column_config.Column(width="medium"),
        },
        height=1000,
        width=1600,
        hide_index=True,
    )
    edited_data["path"] = selected_data["path"]

    edited_data["data"] = calc_data(edited_data["data"])
    save(edited_df, edited_data, settings)
    if col1.button("Save"):
        st.cache_data.clear()
        edited_data["data"] = calc_data(edited_data["data"])
        save(edited_df, edited_data, settings)
    if col2.button("Edit on CSV Editor"):
        os.system("open " + str(selected_data["path"]))
    if col3.button("Reload"):
        st.cache_data.clear()
        st.experimental_rerun()
    if col4.button("Export"):
        st.cache_data.clear()
        edited_data["data"] = calc_data(edited_data["data"])
        export(edited_df, edited_data, settings)
        st.experimental_rerun()
