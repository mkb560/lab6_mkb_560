import pandas as pd
import numpy as np
import mysql.connector
import config
# this script identifies wells with spatial outliers (maybe caused by typo in PDF, data reader process and etc) in their latitude and longitude values, and updates them to be closer to the median location of wells in the same county. 
def fix_spatial_outliers():
    print("Connecting to database...")
    conn = mysql.connector.connect(
        host=config.MYSQL_HOST,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE
    )
    
    query = "SELECT id, county, latitude, longitude FROM well_info WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    df = pd.read_sql(query, conn)
    
    updates_to_make = []
    
    std_threshold = 3.0

    print(f"Loaded {len(df)} wells. Analyzing by county...")

    for county, group in df.groupby('county'):
        if len(group) < 3:
            continue
            
        lat_median = group['latitude'].median()
        lon_median = group['longitude'].median()
        
        lat_std = group['latitude'].std()
        lon_std = group['longitude'].std()
        
        if pd.isna(lat_std) or lat_std == 0 or pd.isna(lon_std) or lon_std == 0:
            continue
        for index, row in group.iterrows():
            lat = row['latitude']
            lon = row['longitude']
            well_id = row['id']
            lat_z_score = abs(lat - lat_median) / lat_std
            lon_z_score = abs(lon - lon_median) / lon_std
        
            # North Dakota latitudes are ~45 to 49. Longitudes are ~ -96 to -105.
            is_impossible_location = (lat < 40 or lat > 55) or (lon > -90 or lon < -115)
            

            if lat_z_score > std_threshold or lon_z_score > std_threshold or is_impossible_location:
                # Generate a super small random noise
                noise_lat = np.random.uniform(-0.005, 0.005)
                noise_lon = np.random.uniform(-0.005, 0.005)
                
                new_lat = lat_median + noise_lat
                new_lon = lon_median + noise_lon
                
                updates_to_make.append((float(new_lat), float(new_lon), well_id))
                
                print(f"[{county}] Outlier fixed for Well ID {well_id}: "
                      f"Moved ({lat:.4f}, {lon:.4f}) -> ({new_lat:.4f}, {new_lon:.4f})")

    if updates_to_make:
        cursor = conn.cursor()
        update_query = "UPDATE well_info SET latitude = %s, longitude = %s WHERE id = %s"
        cursor.executemany(update_query, updates_to_make)
        conn.commit()
        cursor.close()
        print(f"Successfully updated {len(updates_to_make)} outlier wells in the database!")
    else:
        print("Analysis complete. No outliers found exceeding the threshold!")

    conn.close()

if __name__ == "__main__":
    fix_spatial_outliers()