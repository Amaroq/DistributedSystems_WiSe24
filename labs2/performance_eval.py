import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

raw_data = pd.read_csv('logs/test_partitions_log_11-27-202416-09-08.csv')

perfect_df = raw_data.loc[(raw_data['scenario'] == 'perfect')]
easy_df = raw_data.loc[(raw_data['scenario'] == 'easy')]

# scatter plots

indexlist = ['2', '3', '4', '5', '6', '7', '8', '9']

plot = easy_df.plot.scatter('number of servers', 'time to reach consistency in partitions', c = 'number of entries',colormap ='jet')
plot.set_xticks(range(2,10))
plot.set_xticklabels(["%s" % item for item in indexlist])
fig = plot.get_figure()
fig.savefig('plots/easy_partitions.png')

plot = perfect_df.plot.scatter('number of servers', 'time to reach consistency in partitions', c = 'number of entries',colormap ='jet')
plot.set_xticks(range(2,10))
plot.set_xticklabels(["%s" % item for item in indexlist])
fig = plot.get_figure()
fig.savefig('plots/perfect_partitions.png')

plot = easy_df.plot.scatter('number of servers', 'time until consistency on servers', c = 'number of entries',colormap ='jet')
plot.set_xticks(range(2,10))
plot.set_xticklabels(["%s" % item for item in indexlist])
fig = plot.get_figure()
fig.savefig('plots/easy_servers.png')

plot = perfect_df.plot.scatter('number of servers', 'time until consistency on servers', c = 'number of entries',colormap ='jet')
plot.set_xticks(range(2,10))
plot.set_xticklabels(["%s" % item for item in indexlist])
fig = plot.get_figure()
fig.savefig('plots/perfect_servers.png')

# histograms

perfect_df_ten_entries = perfect_df.loc[(perfect_df['number of entries'] == 10)]
perfect_df_ten_entries_sliced = perfect_df_ten_entries[['number of servers', 'time to reach consistency in partitions']]
perfect_df_ten_entries_sliced = perfect_df_ten_entries_sliced.groupby(['number of servers']).mean()
perfect_df_twenty_entries = perfect_df.loc[(perfect_df['number of entries'] == 20)]
perfect_df_twenty_entries_sliced = perfect_df_twenty_entries[['number of servers', 'time to reach consistency in partitions']]
perfect_df_twenty_entries_sliced = perfect_df_twenty_entries_sliced.groupby(['number of servers']).mean()
perfect_df_thirty_entries = perfect_df.loc[(perfect_df['number of entries'] == 30)]
perfect_df_thirty_entries_sliced = perfect_df_thirty_entries[['number of servers', 'time to reach consistency in partitions']]
perfect_df_thirty_entries_sliced = perfect_df_thirty_entries_sliced.groupby(['number of servers']).mean()
perfect_df_forty_entries = perfect_df.loc[(perfect_df['number of entries'] == 40)]
perfect_df_forty_entries_sliced = perfect_df_forty_entries[['number of servers', 'time to reach consistency in partitions']]
perfect_df_forty_entries_sliced = perfect_df_forty_entries_sliced.groupby(['number of servers']).mean()
perfect_df_fifty_entries = perfect_df.loc[(perfect_df['number of entries'] == 50)]
perfect_df_fifty_entries_sliced = perfect_df_fifty_entries[['number of servers', 'time to reach consistency in partitions']]
perfect_df_fifty_entries_sliced = perfect_df_fifty_entries_sliced.groupby(['number of servers']).mean()

easy_df_ten_entries = easy_df.loc[(easy_df['number of entries'] == 10)]
easy_df_ten_entries_sliced = easy_df_ten_entries[['number of servers', 'time to reach consistency in partitions']]
easy_df_ten_entries_sliced = easy_df_ten_entries_sliced.groupby(['number of servers']).mean()
easy_df_twenty_entries = easy_df.loc[(easy_df['number of entries'] == 20)]
easy_df_twenty_entries_sliced = easy_df_twenty_entries[['number of servers', 'time to reach consistency in partitions']]
easy_df_twenty_entries_sliced = easy_df_twenty_entries_sliced.groupby(['number of servers']).mean()
easy_df_thirty_entries = easy_df.loc[(easy_df['number of entries'] == 30)]
easy_df_thirty_entries_sliced = easy_df_thirty_entries[['number of servers', 'time to reach consistency in partitions']]
easy_df_thirty_entries_sliced = easy_df_thirty_entries_sliced.groupby(['number of servers']).mean()
easy_df_forty_entries = easy_df.loc[(easy_df['number of entries'] == 40)]
easy_df_forty_entries_sliced = easy_df_forty_entries[['number of servers', 'time to reach consistency in partitions']]
easy_df_forty_entries_sliced = easy_df_forty_entries_sliced.groupby(['number of servers']).mean()
easy_df_fifty_entries = easy_df.loc[(easy_df['number of entries'] == 50)]
easy_df_fifty_entries_sliced = easy_df_fifty_entries[['number of servers', 'time to reach consistency in partitions']]
easy_df_fifty_entries_sliced = easy_df_fifty_entries_sliced.groupby(['number of servers']).mean()


data_perfect = {
    '10 entries': perfect_df_ten_entries_sliced['time to reach consistency in partitions'],
    '20 entries': perfect_df_twenty_entries_sliced['time to reach consistency in partitions'],
    '30 entries': perfect_df_thirty_entries_sliced['time to reach consistency in partitions'],
    '40 entries': perfect_df_forty_entries_sliced['time to reach consistency in partitions'],
    '50 entries': perfect_df_fifty_entries_sliced['time to reach consistency in partitions']
}
data_easy = {
    '10 entries': easy_df_ten_entries_sliced['time to reach consistency in partitions'],
    '20 entries': easy_df_twenty_entries_sliced['time to reach consistency in partitions'],
    '30 entries': easy_df_thirty_entries_sliced['time to reach consistency in partitions'],
    '40 entries': easy_df_forty_entries_sliced['time to reach consistency in partitions'],
    '50 entries': easy_df_fifty_entries_sliced['time to reach consistency in partitions']
}
number_of_servers = [2,3,4,5,6,7,8,9]

bar_width = 0.2
x = np.arange(len(number_of_servers))

fig, axes = plt.subplots(1, 2, figsize=(17, 8), sharey=True)

for i, (label, values) in enumerate(data_perfect.items()):
    axes[0].bar(x + i * bar_width, values, width=bar_width, label=label)

axes[0].set_title('perfect scenario')
axes[0].set_xlabel('number of servers')
axes[0].set_ylabel('time to reach consistency in partitions (mean)')
axes[0].set_xticks(x + bar_width, number_of_servers)
axes[0].legend()
axes[0].grid(axis='y', linestyle='--', alpha=0.7)

for i, (label, values) in enumerate(data_easy.items()):
    axes[1].bar(x + i * bar_width, values, width=bar_width, label=label)
axes[1].set_title('easy scenario')
axes[1].set_xlabel('number of servers')
axes[1].set_xticks(x + bar_width)
axes[1].set_xticklabels(number_of_servers)
axes[1].legend()
axes[1].grid(axis='y', linestyle='--', alpha=0.7)

plt.tight_layout()
plt.savefig('plots/partition_consistency.png')

perfect_df_ten_entries = perfect_df.loc[(perfect_df['number of entries'] == 10)]
perfect_df_ten_entries_sliced = perfect_df_ten_entries[['number of servers', 'time until consistency on servers']]
perfect_df_ten_entries_sliced = perfect_df_ten_entries_sliced.groupby(['number of servers']).mean()
perfect_df_twenty_entries = perfect_df.loc[(perfect_df['number of entries'] == 20)]
perfect_df_twenty_entries_sliced = perfect_df_twenty_entries[['number of servers', 'time until consistency on servers']]
perfect_df_twenty_entries_sliced = perfect_df_twenty_entries_sliced.groupby(['number of servers']).mean()
perfect_df_thirty_entries = perfect_df.loc[(perfect_df['number of entries'] == 30)]
perfect_df_thirty_entries_sliced = perfect_df_thirty_entries[['number of servers', 'time until consistency on servers']]
perfect_df_thirty_entries_sliced = perfect_df_thirty_entries_sliced.groupby(['number of servers']).mean()
perfect_df_forty_entries = perfect_df.loc[(perfect_df['number of entries'] == 40)]
perfect_df_forty_entries_sliced = perfect_df_forty_entries[['number of servers', 'time until consistency on servers']]
perfect_df_forty_entries_sliced = perfect_df_forty_entries_sliced.groupby(['number of servers']).mean()
perfect_df_fifty_entries = perfect_df.loc[(perfect_df['number of entries'] == 50)]
perfect_df_fifty_entries_sliced = perfect_df_fifty_entries[['number of servers', 'time until consistency on servers']]
perfect_df_fifty_entries_sliced = perfect_df_fifty_entries_sliced.groupby(['number of servers']).mean()

easy_df_ten_entries = easy_df.loc[(easy_df['number of entries'] == 10)]
easy_df_ten_entries_sliced = easy_df_ten_entries[['number of servers', 'time until consistency on servers']]
easy_df_ten_entries_sliced = easy_df_ten_entries_sliced.groupby(['number of servers']).mean()
easy_df_twenty_entries = easy_df.loc[(easy_df['number of entries'] == 20)]
easy_df_twenty_entries_sliced = easy_df_twenty_entries[['number of servers', 'time until consistency on servers']]
easy_df_twenty_entries_sliced = easy_df_twenty_entries_sliced.groupby(['number of servers']).mean()
easy_df_thirty_entries = easy_df.loc[(easy_df['number of entries'] == 30)]
easy_df_thirty_entries_sliced = easy_df_thirty_entries[['number of servers', 'time until consistency on servers']]
easy_df_thirty_entries_sliced = easy_df_thirty_entries_sliced.groupby(['number of servers']).mean()
easy_df_forty_entries = easy_df.loc[(easy_df['number of entries'] == 40)]
easy_df_forty_entries_sliced = easy_df_forty_entries[['number of servers', 'time until consistency on servers']]
easy_df_forty_entries_sliced = easy_df_forty_entries_sliced.groupby(['number of servers']).mean()
easy_df_fifty_entries = easy_df.loc[(easy_df['number of entries'] == 50)]
easy_df_fifty_entries_sliced = easy_df_fifty_entries[['number of servers', 'time until consistency on servers']]
easy_df_fifty_entries_sliced = easy_df_fifty_entries_sliced.groupby(['number of servers']).mean()

data_perfect = {
    '10 entries': perfect_df_ten_entries_sliced['time until consistency on servers'],
    '20 entries': perfect_df_twenty_entries_sliced['time until consistency on servers'],
    '30 entries': perfect_df_thirty_entries_sliced['time until consistency on servers'],
    '40 entries': perfect_df_forty_entries_sliced['time until consistency on servers'],
    '50 entries': perfect_df_fifty_entries_sliced['time until consistency on servers']
}
data_easy = {
    '10 entries': easy_df_ten_entries_sliced['time until consistency on servers'],
    '20 entries': easy_df_twenty_entries_sliced['time until consistency on servers'],
    '30 entries': easy_df_thirty_entries_sliced['time until consistency on servers'],
    '40 entries': easy_df_forty_entries_sliced['time until consistency on servers'],
    '50 entries': easy_df_fifty_entries_sliced['time until consistency on servers']
}

bar_width = 0.2
x = np.arange(len(number_of_servers))

fig, axes = plt.subplots(1, 2, figsize=(17, 8), sharey=True)

for i, (label, values) in enumerate(data_perfect.items()):
    axes[0].bar(x + i * bar_width, values, width=bar_width, label=label)

axes[0].set_title('perfect scenario')
axes[0].set_xlabel('number of servers')
axes[0].set_ylabel('time until consistency on servers (mean)')
axes[0].set_xticks(x + bar_width, number_of_servers)
axes[0].legend()
axes[0].grid(axis='y', linestyle='--', alpha=0.7)

for i, (label, values) in enumerate(data_easy.items()):
    axes[1].bar(x + i * bar_width, values, width=bar_width, label=label)
axes[1].set_title('easy scenario')
axes[1].set_xlabel('number of servers')
axes[1].set_xticks(x + bar_width)
axes[1].set_xticklabels(number_of_servers)
axes[1].legend()
axes[1].grid(axis='y', linestyle='--', alpha=0.7)

plt.tight_layout()
plt.savefig('plots/server_consistency.png')