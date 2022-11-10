# -*- coding: utf-8 -*-
"""
Created on Fri Nov  4 11:55:09 2022
Last Edit 11/9/2022
Baidu Geocoding V1.0
@author: zhangliyao
"""

import requests
import numpy as np
import streamlit as st
import pandas as pd
from stqdm import stqdm
from GCS_Conversion import gcj2wgs

def main():
    st.set_page_config(
    page_title="Geocoding",
    page_icon="📍",
    initial_sidebar_state="expanded",
    )
    st.header('Geocoding地理编码工具')
    st.caption('根据地址信息调用百度API反查坐标，需要用户提供开发者密钥，每日每个密钥的请求额度为5000次')
    st.sidebar.title("帮助与反馈")
    st.sidebar.info(
    """
    【Geocoding地理编码工具使用说明】<https://docs.qq.com/doc/DVWlTSGR5ZEJqYktk>
    
    如果您有任何问题或建议，请联系：创新与研发中心-萧俊瑶
    """
    )

    data_file = st.file_uploader("上传数据文件", type=['csv','xlsx','xls'], help='文件格式要求：第一行为表头信息，excel文件默认读取第一个工作簿', key='data')
    keys_file = st.file_uploader("上传密钥文件", type=['csv','xlsx','xls'], help='文件格式要求：含表头信息，密钥存储在第一列', key='keys')

    if data_file and keys_file:
        with st.spinner('正在读取文件...'):
            frame_list = read_files([data_file, keys_file])
            continue_flag = get_key_usage(frame_list)
        if continue_flag:
            with st.form(key='parameter'):
                city = st.text_input('城市名称', help='输入数据所在城市名称，如深圳市')
                column_duplicate = st.multiselect('选择字段用于数据去重(可多选)', options=frame_list[0].columns, help='请选择根据哪些信息去重，如统一社会信用代码', key='drop_duplicates')
                column_geocoding = st.selectbox('选择字段用于地理编码', options=frame_list[0].columns, help='请选择根据哪一列信息地理编码，如最新年报地址', key='geocoding')
                preview = st.checkbox("结果预览", value=False, key='preview_box')
                run = st.form_submit_button(label='运行')
            
            if run:
                #数据去重
                if column_duplicate:
                    frame_list[0].drop_duplicates(subset=column_duplicate, keep='first', inplace=True)
                    
                if not city:
                    st.error('请输入城市名称')
                elif not column_geocoding:
                    st.error('请选择用于地理编码的字段')
                else:
                    #密钥存储
                    key_list = []
                    for i in range(len(frame_list[1])):
                        key = frame_list[1].iloc[i,0]
                        key_list.append(key)
                        
                    #循环地理编码
                    key_index = num_iters = num_errors = 0
                    address_index = frame_list[0].columns.get_loc(column_geocoding)

                    for i in stqdm(range(len(frame_list[0]))):
                        if num_iters == 5000:
                            key_index += 1
                            num_iters = 0
                            st.write('已切换key')
                        current_key = key_list[key_index]
                        address = frame_list[0].iloc[i, address_index]
                        try:
                            url = 'https://api.map.baidu.com/geocoding/v3/?address='+address+'&city='+city+'&ret_coordtype=gcj02ll&output=json&ak='+current_key
                            data = requests.get(url)
                            data.close()
                            coords = data.json()
                            frame_list[0].at[i, 'gcj02_x'] = coords['result']['location']['lng']
                            frame_list[0].at[i, 'gcj02_y'] = coords['result']['location']['lat']
                            frame_list[0].at[i, 'confidence'] = coords['result']['confidence']
                            frame_list[0].at[i, 'comprehension'] = coords['result']['comprehension']
                        except:
                            num_errors += 1
                        num_iters += 1
                    
                    #转坐标
                    with st.spinner('正在转换坐标...'):
                        df_result_baidu = to_wgs(frame_list[0])
                        
                    #结果预览
                    if preview:
                        st.dataframe(df_result_baidu)
                        
                    #数据下载
                    csv = convert_df(df_result_baidu)
                    st.download_button(
                        label="下载结果并退出",
                        data=csv,
                        file_name='百度地理编码结果.csv',
                        mime='csv',
                        )
                    
@st.cache()
def convert_df(df):
    return df.to_csv(index=False).encode('UTF-8')
                
def to_wgs(df):
    if df.columns.__contains__('gcj02_x'):
        lon = np.empty([len(df["gcj02_x"]), 1], dtype=float)
        lat = np.empty([len(df["gcj02_y"]), 1], dtype=float)   
        for i in range(len(df["gcj02_x"])):
            lon[i], lat[i] = gcj2wgs(df["gcj02_x"][i], df["gcj02_y"][i])
        df["wgs_x"] = lon
        df["wgs_y"] = lat
        del lon
        del lat

    return df

@st.cache(allow_output_mutation=True)
def read_files(file_list):
    '''
    Parameters
    ----------
    file_list : list
        上传的数据文件和密钥文件.

    Returns
    -------
    frame_list : list
        读取为dataframe后的数据文件和密钥文件.
    '''
    frame_list = []
    for file in file_list:
        file_type = get_file_type(file)
        if file_type == 'csv':
            try:
                df = pd.read_csv(file)
            except:
                df = pd.read_csv(file, encoding='gb18030')
        else:
            df = pd.read_excel(file)
        frame_list.append(df)
    return frame_list
    
def get_file_type(file):
    if file.name.endswith('csv'):
        return 'csv'
    else:
        return 'excel'
    
def get_key_usage(frame_list):
    num_data = len(frame_list[0])
    num_keys = len(frame_list[1])
    st.write('上传数据'+str(num_data)+'条，上传密钥'+str(num_keys)+'个')
    if num_keys*5000 >= num_data:
        st.success('文件读取成功！')
        return True
    else:
        st.warning('密钥额度不足，请修改文件后再上传')
        return False
    
if __name__ == "__main__":
    main()