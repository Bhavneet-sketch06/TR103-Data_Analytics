import joblib
import pandas as pd

# Load the trained Random Forest model
model = joblib.load("models/sales_model.pkl")


def predict_sales(
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
    shipping_days
):

    input_data = pd.DataFrame({
        "Category": [category],
        "Sub-Category": [sub_category],
        "Ship Mode": [ship_mode],
        "Region": [region],
        "State": [state],
        "Segment": [segment],
        "Quantity": [quantity],
        "Discount": [discount],
        "Profit": [profit],
        "Year": [year],
        "Month": [month],
        "Shipping Days": [shipping_days]
    })

    prediction = model.predict(input_data)

    return round(prediction[0], 2)


if __name__ == "__main__":

    predicted_sales = predict_sales(
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
        shipping_days=4
    )

    print("Predicted Sales: $", predicted_sales)