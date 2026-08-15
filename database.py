import sqlite3
import pandas as pd

# Connect to SQLite database
connection = sqlite3.connect("sales_predictions.db")

# Create a cursor object
cursor = connection.cursor()


# =====================================================
# Create Database Table
# =====================================================

def create_database():

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            category TEXT,

            sub_category TEXT,

            ship_mode TEXT,

            region TEXT,

            state TEXT,

            segment TEXT,

            quantity INTEGER,

            discount REAL,

            profit REAL,

            year INTEGER,

            month INTEGER,

            shipping_days INTEGER,

            predicted_sales REAL

        )
    """)

    connection.commit()

    print("Predictions table created successfully!")


# =====================================================
# Insert Prediction into Database
# =====================================================

def insert_prediction(
    category,
    sub_category,
    ship_mode,
    region,
    state,
    segment,
    quantity,
    discount,
    profit,
    year,
    month,
    shipping_days,
    predicted_sales
):

    cursor.execute(
        """
        INSERT INTO predictions (

            category,
            sub_category,
            ship_mode,
            region,
            state,
            segment,
            quantity,
            discount,
            profit,
            year,
            month,
            shipping_days,
            predicted_sales

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,

        (
            category,
            sub_category,
            ship_mode,
            region,
            state,
            segment,
            quantity,
            discount,
            profit,
            year,
            month,
            shipping_days,
            predicted_sales
        )

    )

    connection.commit()

    print("Prediction saved successfully!")


# =====================================================
# View All Predictions
# =====================================================

def view_predictions():

    query = "SELECT * FROM predictions"

    df = pd.read_sql_query(query, connection)

    return df


# =====================================================
# Testing Section
# =====================================================

if __name__ == "__main__":

    create_database()

    insert_prediction(
        category="Technology",
        sub_category="Phones",
        ship_mode="Second Class",
        region="West",
        state="California",
        segment="Consumer",
        quantity=3,
        discount=0.20,
        profit=120,
        year=2017,
        month=8,
        shipping_days=4,
        predicted_sales=959.30
    )

    print("\nPrediction History:\n")

    print(view_predictions())
    
# =====================================================
# Delete All Predictions
# =====================================================

def delete_history():

    cursor.execute("DELETE FROM predictions")

    connection.commit()

    print("Prediction history deleted successfully!")
    
if __name__ == "__main__":

    create_database()

    print(view_predictions())