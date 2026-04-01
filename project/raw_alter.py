import pymysql

conn = pymysql.connect(host='127.0.0.1', user='root', password='root', database='hotel_db')
cursor = conn.cursor()
try:
    cursor.execute("ALTER TABLE food_item ADD COLUMN image_url VARCHAR(255)")
except Exception as e: print("skip1")
try:
    cursor.execute("ALTER TABLE food_order ADD COLUMN custom_request VARCHAR(255)")
except Exception as e: print("skip2")
try:
    cursor.execute("ALTER TABLE food_order MODIFY food_item_id INT NULL")
except Exception as e: print("skip3")
try:
    cursor.execute("UPDATE food_item SET image_url='https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=400&q=80' WHERE name='Club Sandwich'")
    cursor.execute("UPDATE food_item SET image_url='https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=400&q=80' WHERE name='Margherita Pizza'")
    cursor.execute("UPDATE food_item SET image_url='https://images.unsplash.com/photo-1550304943-4f24f54ddde9?w=400&q=80' WHERE name='Caesar Salad'")
except Exception as e: print("skip4")
conn.commit()
conn.close()
print("DONE DB ALTER")
