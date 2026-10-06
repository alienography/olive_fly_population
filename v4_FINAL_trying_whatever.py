# -*- coding: utf-8 -*-
"""
Created on Thu Feb 26 17:13:04 2026

@author: simme
"""

#v4 - final version
# plots a heatmap of olive fruit flies for each month, for samos, and
# compiles all the seperate plots onto one plot
# saves to ./heat maps/


# importing relevant packages
import geopandas as gpd
import pandas as pd
import fiona
import shapely
from shapely.geometry import Point, LineString, shape, Polygon
from io import StringIO
from pathlib import Path
import os
import numpy as np
from datetime import datetime, timedelta

import matplotlib

from scipy.stats import binned_statistic_2d

# import mapping packages
import matplotlib.pyplot as plt
from matplotlib.pyplot import subplots, savefig, close

# so define whether traps are sprayed or not sprayed based on dates
# then compare averages to original value, and averages of sprayed vs. non-sprayed
# basically

# take 2022 for example and try to figure out which traps were sprayed vs.
# which weren't for example

# ============= READ IN DATA =============
# first need to rearrange trap data, because it's structured in a horrible way
# actually do i?

# reading in trap data
trap_data = pd.read_excel('../../Samos 2022-2024-20251120T120022Z-1-001/Samos 2022-2024/Traps Samos 2022-2024.xlsx',
                          sheet_name='2022', usecols=['Area', 'N. of Trap', 'Longitude', 'Latitude']#, header=[0, 1]
                          )


# read in olive fly number data
fly_numbers = pd.read_excel('../../Samos 2022-2024-20251120T120022Z-1-001/Samos 2022-2024/Traps Samos 2022-2024.xlsx',
                          sheet_name=['2022', '2023', '2024'], dtype={1: 'float64'}, header=[0, 1]
                          )

# read in regions of samos - DONE WITH FINISHED REGIONS
samos_regions = gpd.read_file('../MY_INPUTS/samos_regions.gpkg')

samos_regions = samos_regions.to_crs('EPSG:4326')



# set area and trap number as a multiindex
for sheet in fly_numbers:
    fly_numbers[sheet] = fly_numbers[sheet].set_index([('Area', 'Unnamed: 0_level_1'), 
                                                       ('N. of Trap', 'Unnamed: 1_level_1')]
                                                       )

# combine the different years into one year
merged_flies = pd.concat(fly_numbers.values(), axis=1)

# get rid of duplicate latitude, longitude & altitude columns
merged_flies = merged_flies.loc[:, ~merged_flies.columns.duplicated()]

# rename the indices pt. II
merged_flies.index.set_names(['Area', 'N. of Trap'], inplace=True)

# label the different levels of the header
merged_flies.columns.names = ['Date', 'Type']

# take out either total numbers or female fly numbers
total_cols = merged_flies.columns[
              merged_flies.columns.get_level_values('Type') != 'Female']  

total_data = merged_flies[total_cols].copy()

total_data.columns = total_data.columns.droplevel('Type')


# make the dataframe into point data with geometries
spray_data_gdb = gpd.GeoDataFrame(trap_data, geometry=gpd.points_from_xy(
                                  trap_data[('Longitude')],
                                  trap_data[('Latitude')]),
                                  crs='EPSG:4326')
print("Successfully made geometries of the trap locations") 

# add regions to the data
spray_data_regions = gpd.sjoin(
    spray_data_gdb,
    samos_regions,
    predicate='intersects')

# drop unnecessary stuff
spray_data_regions = spray_data_regions.drop(['index_right'], axis=1)

# set new index
spray_data_new_i = spray_data_regions.set_index(['Area', 'N. of Trap'])

# merge the olive fly numbers with the georeferenced points
olive_fly_regions = total_data.join(
    spray_data_new_i,
    how='left',
    rsuffix='drop'
    )

# drop unnecessary shiz
olive_fly_total = olive_fly_regions.drop(columns=['Longitudedrop', 'Latitudedrop', 'EKTASH', 'PERIMETROS', 'Longitude', 'Latitude', 'Altitude'])

# remove all points belonging to ikaria cause idc
no_ikaria = olive_fly_total.index[
              olive_fly_total['layer'].notna()] 

# "
olive_no_ikaria = olive_fly_total.loc[no_ikaria].copy()

olive_no_ikaria.to_excel('./dataforheat.xlsx')

olive_no_ikaria.columns = pd.to_datetime(olive_no_ikaria.columns, errors='ignore')

date_cols = olive_no_ikaria.columns[pd.to_datetime(olive_no_ikaria.columns, errors='coerce').notna()] 

date_cols = pd.to_datetime(date_cols)

month_list = date_cols.strftime('%y-%m').unique()


# set font
graphfont = {'fontname':'Arial'}

mean_dict = {}
sum_dict = {}

# for each unique combination of month and year, find the mean & sum
for date in month_list:
    
    # drop the date, only keep month and year
    choose_date = datetime.strptime(date, '%y-%m')
    
    # store these variables
    choose_month = choose_date.month
    choose_year = choose_date.year
    
    select_cols = date_cols[(date_cols.month == choose_month) & (date_cols.year == choose_year)]
    
    month_dataset = olive_no_ikaria.loc[:, select_cols]
    
    month_dataset['sum'] = month_dataset.sum(axis=1)
    
    month_dataset['mean'] = month_dataset.mean(axis=1)
    
    mean_dict[date] = month_dataset['mean']
    
    sum_dict[date] = month_dataset['sum']

# create a new dataframe with these calculations
month_df = pd.DataFrame(sum_dict)

#month_long = month_df.unstack(columns=)

# reassign the geometry back to the new dataframe
month_df['geometry'] = olive_no_ikaria['geometry']

month_df['layer'] = olive_no_ikaria['layer']
#month_df.to_excel('./testme.xlsx')

# set the column names to string objects rather than datetime
month_df.columns = month_df.columns.astype(str)

month_gdf = gpd.GeoDataFrame(month_df, geometry='geometry', crs='EPSG:4326')

# save as a geopackage
month_gdf.to_file('./new_olive.gpkg', driver='GPKG')

#%% making chloropleth

# initialise a plot
fig, axs = subplots(5, 3, figsize=(15, 10))
(my_axa, my_axb, my_axc), (my_axd, my_axe, my_axf), (my_axg, my_axh, my_axi), (my_axj, my_axk, my_axl), (my_axm, my_axn, my_axo) = axs

axs = axs.flatten()

# define the maximum value
month_max = month_gdf.max()

ax_list = axs
fig.tight_layout(pad=3)

# set the layout
fig.tight_layout(rect=[0, 0, .9, 1])

month_strings = month_gdf.columns[:-2]

norm = plt.Normalize(vmin=0, vmax=1200)

# set the colourmap
cmat = plt.get_cmap('rocket_r').copy()
cmat.set_bad(alpha=0)

fig.colorbar(matplotlib.cm.ScalarMappable(norm=norm, cmap=cmat),
             ax=axs, shrink=0.6)

i = 0

# for each month/year combination
for month in month_strings:
    
    # the axis is the next axis in the plot
    choose_ax = axs[i]
    
    # select relevant month
    month_cols = month_gdf.columns[
        month_gdf.columns == month]
    
    # select geometry
    months_ii = month_gdf.columns[
        month_gdf.columns == 'geometry']
    
    relevant_month = month_gdf[(month_cols | months_ii)].copy()
    
    month_numeric = month_gdf[(month_cols)].copy()
    
    # find x and y co-ordinates of geometry
    relevant_month['x'] = relevant_month.geometry.x
    relevant_month['y'] = relevant_month.geometry.y
    
    # this was for test
    #relevant_month.to_excel('./iwannasee.xlsx')
    
    # plot based on 40 bins of values
    heatmap, xedges, yedges, _ = binned_statistic_2d(
        relevant_month['x'],
        relevant_month['y'],
        relevant_month[month],
        statistic='sum',
        bins=40
        )
    
    # find the centre of samos extremities
    xcentres = (xedges[:-1] + xedges[1:]) / 2
    ycentres = (yedges[:-1] + yedges[1:]) / 2
    
    # define the centre points
    xx, yy = np.meshgrid(xcentres, ycentres)
    
    # define a set of points based on samos' geometry
    points=gpd.GeoSeries(
        [Point(x, y) for x, y in zip(xx.ravel(), yy.ravel())],
        crs=samos_regions.crs
        )
    
    # use the point geodatabase to define the edges of samos
    island_outline = samos_regions.unary_union
    inside = points.within(island_outline).values.reshape(xx.shape)
    
    # crop the heatmap based on the outline of samos
    heatmap_mask = heatmap.T.copy()
    heatmap_mask[~inside] = np.nan
    heatmap_mask = np.ma.masked_invalid(heatmap_mask)
    
    #not sure i want to do this ? -> cause kallithea just has no data, not 0.#heatmap = np.nan_to_num(heatmap, nan=0)
    
    choose_ax.pcolormesh(
        xedges,
        yedges,
        heatmap_mask,
        cmap=cmat,
        norm=norm,
        shading='auto'
        )
    
    # plot the boundary of samos
    choose_ax.set_aspect('equal')
    samos_regions.boundary.plot(ax=choose_ax, 
                                color='black',
                                linewidth=0.5
                                )
    
    # set a title
    print_date = datetime.strptime(month, '%y-%m')
    
    # re-organise the title so it's not year first
    print_reorganised = print_date.strftime('%B %Y')
    
    # set graph title
    choose_ax.set_title(f'{print_reorganised}', **graphfont, size=16)
    
    choose_ax.axis('off')
    
    # save figure
    savefig(f'./heat maps/new_test.png', bbox_inches='tight', pad_inches=0, dpi=600)
    i = i + 1

    #plt.cla()
    #plt.clf()
    

