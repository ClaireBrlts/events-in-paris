import streamlit as st
import pandas as pd
import pydeck as pdk
import os
import datetime
from geopy.geocoders import Nominatim
import openrouteservice

os.environ["MAPBOX_API_KEY"] = "pk.eyJ1IjoiY2xhaXJlYnJsdHMiLCJhIjoiY21jazltcWV1MGJheDJpc2FnM2Y3bzNlMiJ9.HLCDZEtughQ3GYPzqrv1CA"
ORS_API_KEY = '5b3ce3597851110001cf6248386184f778cf4a6d819d5a4422fad8dc'

# Load data
df = pd.read_csv('C:/Users/clair/IronHack/Final Project/events-in-paris/Jupyter Notebooks/events_final_streamlit_dash.csv', dtype={8: str})
df["date"] = pd.to_datetime(df["date"])

def color_temp(temp):
    if temp <= 10:
        return "blue"
    elif temp <= 20:
        return "green"
    elif temp <= 30:
        return "orange"
    else:
        return "red"
    
def color_uv(uv):
    if uv <= 2:
        return "grey"
    elif uv <= 4:
        return "green"
    elif uv <= 6:
        return "orange"
    else:
        return "red"
    
def color_rain(rain):
    if rain == 0:
        return "green"
    elif rain <=2:
        return "magenta"
    elif rain <=4:
        return "orange"
    else:
        return "red"

selected_date = st.date_input("Select date", value=datetime.date.today())
filtered_df = df[df["date"].dt.date == selected_date]

if selected_date > (datetime.date.today() + datetime.timedelta(days=13)):
    st.write("#### No weather predictions available")
else:
    st.write("#### Weather summary for", selected_date)

    max_temp = int(filtered_df['temperature_2m_max'].iloc[0])
    min_temp = int(filtered_df['temperature_2m_min'].iloc[0])
    uv_index = int(filtered_df['uv_index_max'].iloc[0])
    rain = int(filtered_df['precipitation_hours'].iloc[0])

    st.markdown(
        f"Max Temp: <span style='color:{color_temp(max_temp)}; font-weight:bold'>{max_temp} °C</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"Min Temp: <span style='color:{color_temp(min_temp)}; font-weight:bold'>{min_temp} °C</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"UV Index: <span style='color:{color_uv(uv_index)}; font-weight:bold'>{uv_index} </span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"Rain: <span style='color:{color_rain(rain)}; font-weight:bold'>{rain} h</span>",
        unsafe_allow_html=True,
    )

    
user_location = st.text_input("Enter your departure address or coordinates:")

if user_location and not filtered_df.empty:
    geolocator = Nominatim(user_agent="my_app", timeout=10)
    location = geolocator.geocode(user_location)

    if location:
        st.write(f"Your location: {location.latitude}, {location.longitude}")

        client = openrouteservice.Client(key=ORS_API_KEY)

        dest_coords = filtered_df[['longitude', 'latitude']].values.tolist()
        orig_coord = [location.longitude, location.latitude]

        def get_travel_times(profile):
            try:
                matrix = client.distance_matrix(
                    locations=[orig_coord] + dest_coords,
                    profile=profile,
                    metrics=["duration"],
                    sources=[0],
                    destinations=list(range(1, len(dest_coords) + 1))
                )
                durations = matrix['durations'][0]
                return [round(d / 60) if d is not None else None for d in durations]
            except Exception as e:
                st.error(f"Error with profile {profile}: {e}")
                return [None] * len(dest_coords)

        walk_times = get_travel_times("foot-walking")
        bike_times = get_travel_times("cycling-regular")
        drive_times = get_travel_times("driving-car")

        filtered_df['walk_time_min'] = walk_times
        filtered_df['bike_time_min'] = bike_times
        filtered_df['drive_time_min'] = drive_times

        # 💡 Add travel mode selector
        travel_mode = st.selectbox("Choose your travel mode", options=["walk", "bike", "drive"])
        max_time = st.slider("Max travel time (minutes)", 0, 120, 60)

        # 💡 Create filter based on travel mode and max time
        time_column = f"{travel_mode}_time_min"

        # Only keep rows where travel time is not None and below max
        filtered_df = filtered_df[(filtered_df[time_column].notnull()) & (filtered_df[time_column] <= max_time)]

    else:
        st.error("Could not geocode the location.")


# 1. Identify theme columns
theme_cols = [col for col in filtered_df.columns if col.startswith('theme')]

# 2. Get unique themes across all theme columns (flatten and drop NA)
all_themes = pd.unique(filtered_df[theme_cols].values.ravel())
all_themes = [t for t in all_themes if pd.notna(t)]

# 3. Theme filter multiselect
selected_themes = st.multiselect("Select themes", options=all_themes, default=all_themes)

# 4. Filter events where ANY of the theme columns match selected themes
if selected_themes:
    mask = filtered_df[theme_cols].apply(lambda row: any(t in selected_themes for t in row), axis=1)
    filtered_df = filtered_df[mask]
else:
    # If no themes selected, show none
    filtered_df = filtered_df.iloc[0:0]


if filtered_df.empty:
    st.write("No events found on this date.")
else:
    # Combine themes into one column for tooltip
    filtered_df['themes_combined'] = filtered_df[theme_cols].fillna('').agg(', '.join, axis=1).str.strip(', ').replace('', 'No theme')

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=filtered_df,
        get_position='[longitude, latitude]',
        get_color='[255, 140, 0, 255]',
        get_radius=90,
        pickable=True
    )

    view_state = pdk.ViewState(
        latitude=filtered_df["latitude"].mean(),
        longitude=filtered_df["longitude"].mean(),
        zoom=9,
        pitch=0
    )

    r = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={
            "text": "{titre}\nThemes: {themes_combined}\nWalk: {walk_time_min} min\nBike: {bike_time_min} min\nDrive: {drive_time_min} min"
        },
        map_style='mapbox://styles/mapbox/streets-v12'
    )

    st.pydeck_chart(r)

    # Add a selectbox to pick an event to show details including URL
    event_titles = filtered_df['titre'].tolist()
    selected_event_title = st.selectbox("Select an event to see more details", options=event_titles)

    if selected_event_title:
        selected_event = filtered_df[filtered_df['titre'] == selected_event_title].iloc[0]
        st.markdown(f"### {selected_event['titre']}")
        st.markdown(f"**Thèmes:** {selected_event['themes_combined']}")
        st.markdown(f"**Nom du lieu:** {selected_event['nom_du_lieu']}")
        st.markdown(f"**Intro:** {selected_event['chapeau']}")
        st.markdown(f"**Description:** {selected_event['description']}")     
        st.markdown(f"**Dates:** {selected_event['description_de_la_date']}")
        st.markdown(f"**Prix:** {selected_event['type_de_prix']}")
        st.markdown(f"**Réservation:** {selected_event['type_d_acces']}")
        url = selected_event.get('url', None)
        if url and pd.notna(url):
            st.markdown(f"[Visit the event page]({url})")
        else:
            st.markdown("_No URL available_")

