import pyspark as ps
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
import os
import re
from pyspark.sql.types import StringType
import requests
import mysql.connector

# Creating Spark Session
spark = SparkSession.builder.appName('SBA 350').getOrCreate()

# Reading/loading the Dataset from JSON file
customer_spark = spark.read.load("cdw_sapp_customer.json", format="json")
branch_spark = spark.read.load("cdw_sapp_branch.json", format="json")
credit_spark = spark.read.load("cdw_sapp_credit.json", format="json")

# transforms the passed df's column into title case(initcap)
def tran_cust_title_case(df, column_name):
    return df.withColumn(column_name, initcap(col(column_name)))

# transforms the passed df's column into lower case
def tran_cust_lower_case(df, column_name):
    return df.withColumn(column_name, lower(col(column_name)))

# concats the customer's street and apt numbers into a single column
def concat_cust_street_apt(df, col1, col2):
    return df.withColumn('FULL_STREET_ADDRESS', concat_ws(',', col(col1), col(col2)))

# the cust_phone doesn't have an area code, need to rectify somehow
def tran_phone_num(df, column_name):
    return df.withColumn(column_name, concat(lit('('),
                                             substring(col(column_name), 1, 3),
                                             lit(')'),
                                             substring(col(column_name), 4, 3),
                                             lit('-'),
                                             substring(col(column_name), 7, 4))
                                             .cast('string'))

# checks if the branches zip is null and defaults it to 99999, and if it isn't it returns the branches zip
def tran_branch_zip(df):
    return df.withColumn('BRANCH_ZIP', when(col('BRANCH_ZIP').isNull(), lit(99999)).otherwise(col('BRANCH_ZIP')))

# match cust state to branch state and slice branch phone 3-5 to append to cust phone after 2nd element
custJoinbranch = customer_spark.join(branch_spark, customer_spark.CUST_STATE == branch_spark.BRANCH_STATE, 'left')
customer_fix = custJoinbranch.withColumn('CUST_PHONE', concat(col('CUST_PHONE').substr(1, 2), col('BRANCH_PHONE').substr(3, 3), col('CUST_PHONE').substr(3, 7)))
unwanted_columns = branch_spark.columns
customer_fix = customer_fix.drop(*unwanted_columns).dropDuplicates(['SSN'])

# concat the day, month, year columns into a TIMEID (YYYYMMDD)
def tran_to_timeid(df, day, month, year):
    date_string = concat(
        col(year),
        lpad(col(month), 2, '0'),
        lpad(col(day), 2, '0'))
    return df.withColumn('TIMEID', to_date(date_string, 'yyyyMMdd'))

# transforming the specified columns of the extracted customer df into a new df
tran_cust_spark = customer_fix.transform(tran_cust_title_case, 'FIRST_NAME') \
    .transform(tran_cust_lower_case, 'MIDDLE_NAME') \
    .transform(tran_cust_title_case, 'LAST_NAME') \
    .transform(concat_cust_street_apt, 'APT_NO', 'STREET_NAME') \
    .drop('STREET_NAME', 'APT_NO') \
    .transform(tran_phone_num, 'CUST_PHONE')

# transforming the specified columns of the extracted branch df into a new df
tran_branch_spark = branch_spark.transform(tran_branch_zip) \
    .transform(tran_phone_num, 'BRANCH_PHONE')

# transforming the specified columns of the extracted credit df into a new df
tran_credit_spark = credit_spark.transform(tran_to_timeid, 'DAY', 'MONTH', 'YEAR') \
    .drop('DAY', 'MONTH', 'YEAR')

# create and populate the requisite tables in SQL db creditcard_capstone
tran_cust_spark.write.format("jdbc").options(driver="com.mysql.cj.jdbc.Driver",
                                              user="root",
                                              password="password",
                                              url="jdbc:mysql://localhost:3306/creditcard_capstone",
                                              dbtable="CDW_SAPP_CUSTOMER",
                                              ).mode('overwrite').save()

tran_branch_spark.write.format("jdbc").options(driver="com.mysql.cj.jdbc.Driver",
                                                user="root",
                                                password="password",
                                                url="jdbc:mysql://localhost:3306/creditcard_capstone",
                                                dbtable="CDW_SAPP_BRANCH",
                                                ).mode('overwrite').save()

tran_credit_spark.write.format("jdbc").options(driver="com.mysql.cj.jdbc.Driver",
                                                user="root",
                                                password="password",
                                                url="jdbc:mysql://localhost:3306/creditcard_capstone",
                                                dbtable="CDW_SAPP_CREDIT_CARD",
                                                ).mode('overwrite').save()

# Read the data from the MySQL table
cust_sql = spark.read.format("jdbc").options(driver="com.mysql.cj.jdbc.Driver",
                                             user="root",
                                             password="password",
                                             url="jdbc:mysql://localhost:3306/creditcard_capstone",
                                             dbtable="CDW_SAPP_CUSTOMER"
                                             ).load()
branch_sql = spark.read.format("jdbc").options(driver="com.mysql.cj.jdbc.Driver",
                                               user="root",
                                               password="password",
                                               url="jdbc:mysql://localhost:3306/creditcard_capstone",
                                               dbtable="CDW_SAPP_BRANCH"
                                               ).load()
credit_sql = spark.read.format("jdbc").options(driver="com.mysql.cj.jdbc.Driver",
                                               user="root",
                                               password="password",
                                               url="jdbc:mysql://localhost:3306/creditcard_capstone",
                                               dbtable="CDW_SAPP_CREDIT_CARD"
                                               ).load()

# 4. Functional Requirements - LOAN Application Dataset

# Create a Python program to GET (consume) data from the above API endpoint for the loan application dataset.
bank_url = 'https://raw.githubusercontent.com/platformps/LoanDataset/main/loan_data.json'
response = requests.get(bank_url)
loan_data = response.json()

# Once Python reads data from the API, utilize PySpark to load data into RDBMS (SQL).
# The table name should be CDW-SAPP_loan_application in the database.
# Note: Use the “creditcard_capstone” database.
loan_df = spark.createDataFrame(loan_data)
loan_df.write.format("jdbc").options(driver="com.mysql.cj.jdbc.Driver",
                                     user="root",
                                     password="password",
                                     url="jdbc:mysql://localhost:3306/creditcard_capstone",
                                     dbtable="CDW_SAPP_loan_application",
                                     ).mode('overwrite').save()

# FUNCTIONS
# Clears the terminal screen and displays a title bar.
def display_title_bar():
    os.system('cls')
    print("\t**********************************************")
    print("\t***  Welcome to Chad's Final Project!  ***")
    print("\t**********************************************")


# Gets the user's choice.
def get_user_choice():
    # Let users know what they can do.
    print("\n[1] See a list of customers")
    print("[2] See a list of branches")
    print("[3] See a list of credit card transactions")
    print("[4] See a list of loan applications")
    print("[q] Quit.")
    return input("What would you like to do? ")


# Displays the user's choice.
def show_menu():
    choice = '0'
    display_title_bar()
    while choice != 'q':
        choice = get_user_choice()
        # Respond to the user's choice.
        display_title_bar()
        if choice == '1':
            cust_sql.show()
        elif choice == '2':
            branch_sql.show()
        elif choice == '3':
            credit_sql.show()
        elif choice == '4':
            loan_sql = spark.read.format("jdbc").options(driver="com.mysql.cj.jdbc.Driver",
                                                         user="root",
                                                         password="password",
                                                         url="jdbc:mysql://localhost:3306/creditcard_capstone",
                                                         dbtable="CDW_SAPP_loan_application"
                                                         ).load()
            loan_sql.show()
        elif choice == 'q':
            print("\nThanks for using Chad's Final Project program. Bye!")
        else:
            print("\nI didn't understand that choice.\n")

# CALL TO MAIN FUNCTION
if __name__ == "__main__":
    show_menu()
