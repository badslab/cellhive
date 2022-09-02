from functools import partial
import logging

import pandas as pd

from bokeh.layouts import column, row
from bokeh.models import ColumnDataSource, Range1d, DataTable, TableColumn, ScientificFormatter
from bokeh.models.callbacks import CustomJS
from bokeh.models.widgets import (Select, Div,
                                  Button, AutocompleteInput)
from bokeh.plotting import figure, curdoc
from beehive import config, util, expset
from bokeh.transform import jitter, CategoricalColorMapper

lg = logging.getLogger('GeneExp')
lg.setLevel(logging.DEBUG)
lg.info("startup")

VIEW_NAME = "gene_expression"

curdoc().template_variables['config'] = config
curdoc().template_variables['view_name'] = 'Gene/Protein Expression'

create_widget = partial(util.create_widget, curdoc=curdoc())

datasets = expset.get_datasets(view_name = VIEW_NAME)

args = curdoc().session_context.request.arguments

# WIDGETS
w_div_title_author = Div(text="")

# Dataset

dataset_options = [(k, "{short_title}, {short_author}, {datatype}".format(**v))
                   for k, v in datasets.items()]

w_dataset_id = create_widget("dataset_id", Select, title="Dataset",
                             options=dataset_options,
                             default=dataset_options[0][0],
                             visible=True,height = 30, width = 400)

w_sibling = create_widget("view", Select,
                          options=[],
                          default=w_dataset_id.value,
                          update_url=False,height = 20, width = 150)


def update_sibling_options():
    siblings = expset.get_dataset_siblings(w_dataset_id.value, view_name =  VIEW_NAME)
    sibling_options = []
    # check all organisms
    organisms = []
    for k, v in siblings.items():
        organisms = organisms + [v['organism']]

    if len(list(set(organisms))) == 1:
        for k, v in siblings.items():
            # sname = f"{v['organism']} / {v['datatype']}"
            sname = f"{v['datatype']}"
            sibling_options.append((k, sname))
    else:
        for k, v in siblings.items():
            sname = f"{v['organism']} / {v['datatype']}"
            sibling_options.append((k, sname))

    w_sibling.options = sibling_options


update_sibling_options()


w_gene = create_widget("gene", AutocompleteInput,
                       completions=[], default='APOE', case_sensitive=False, height = 50, width = 150)
w_facet = create_widget("facet", Select, options=[], title="Group by level 1:",height = 50, width = 150)
w_facet2 = create_widget("facet2", Select, options=[], title="Group by level 2:",height = 50, width = 150)
w_facet3 = create_widget("facet3", Select, options=[], title="Jitter points Average:",height = 50, width = 150)
w_download = Button(label='Download', align='end', height = 50, width = 150)
w_download_filename = Div(text="", visible=False,
                          name="download_filename")

# To display text if the gene is not found
w_gene_not_found = Div(text="")

#
# Data handling & updating interface
#


def get_genes():
    """Get available genes for a dataset."""
    dataset_id = w_dataset_id.value
    genes = sorted(list(expset.get_genes(dataset_id)))
    return genes


def update_facets():
    """Update interface for a specific dataset."""
    options = expset.get_facet_options(w_dataset_id.value,only_categorical = True,view_name = VIEW_NAME)
    options_with_skip = expset.get_facet_options(w_dataset_id.value,only_categorical = True, include_skip = True,view_name = VIEW_NAME)
    w_facet.options = options
    w_facet2.options = options
    w_facet3.options = options_with_skip

    w_facet2.options = w_facet2.options + [("--","--")]
    w_facet3.options = w_facet3.options + [("--","--")]

    if w_facet.value not in [x[0] for x in w_facet.options]:
        # set a default
        w_facet.value = w_facet.options[0][0]


    w_facet2.options = list(filter(lambda x: x[0] != w_facet.value,w_facet2.options))
    if w_facet2.value not in [x[0] for x in w_facet2.options]:
        # set a default
        w_facet2.value = w_facet2.options[0][0]

    w_facet.options = list(filter(lambda x: x[0] != w_facet2.value,w_facet.options))

    w_facet3.options = list(filter(lambda x: x[0] != w_facet.value,w_facet3.options))
    w_facet3.options = list(filter(lambda x: x[0] != w_facet2.value or x[0] == "--" ,w_facet3.options))

    if w_facet3.value not in [x[0] for x in w_facet3.options]:
        # set a default
        w_facet3.value =  w_facet3.options[0][0]

    w_facet2.options = list(filter(lambda x: x[0] != w_facet3.value or x[0] == "--",w_facet2.options))
    w_facet.options = list(filter(lambda x: x[0] != w_facet3.value,w_facet.options))


    # w_facet2.value = "--"
    # w_facet3.value = "--"

def update_genes():
    """Update genes widget for a dataset."""
    genes = get_genes()
    w_gene.completions = genes
    if w_gene.value not in genes:
        if 'APOE' in genes:
            w_gene.value = 'APOE'
        else:
            w_gene.value = genes[0]


update_facets()
update_genes()

def get_data() -> pd.DataFrame:
    """Retrieve data from a dataset, gene & facet."""
    global coloring_scheme #name of column for coloring.
    dataset_id = w_dataset_id.value
    gene = w_gene.value
    facet = w_facet.value
    facet2 = w_facet2.value
    facet3 = w_facet3.value

    if w_facet.value == gene:
        coloring_scheme = f'{w_facet.value}_category_y'
    else:
        coloring_scheme = f'{w_facet.value}_x'
    if w_facet2.value == "--":
        coloring_scheme = "cat_value"

    lg.warning(f"!! Getting data for {dataset_id} {facet} {gene}")

    data = expset.get_gene_meta_three_facets(dataset_id,gene,facet,facet2,facet3,view_name = VIEW_NAME)

    #filter NONEs
    data = data.loc[data["cat_value"].str[0] != "NONE"]
    data = data.loc[data["cat_value"].str[1] != "NONE"]
    data = data.loc[data["cat_value"] != "NONE"]

    #for table
    data_no_dups = data.drop_duplicates("cat_value")

    #rename jitter points column
    data = data.rename(columns={f'mean_{facet3}': "jitter"})

    return data,data_no_dups


def get_dataset():
    """Return the current dataset id and record."""
    dataset_id = w_dataset_id.value
    return dataset_id, datasets[dataset_id]

def get_mapper():
    dataset = w_dataset_id.value
    meta = w_facet.value
    dict_colors = expset.get_colors_of_obs(dataset,meta)
    mapper = CategoricalColorMapper(palette = list(dict_colors.values()), factors=list(dict_colors.keys()))
    return mapper

def get_order():
    dataset = w_dataset_id.value
    meta = w_facet.value
    dict_order = expset.get_order_of_obs(dataset,meta)
    ordered_list = sorted(dict_order, key=dict_order.get)
    return ordered_list

#
# Create plot
#
plot = figure(background_fill_color="#efefef", x_range=[],title="Plot",
              toolbar_location='right', tools="save", sizing_mode = "fixed", width = 800, height = 600)


data,data_no_dups = get_data()
warning_experiment = Div(text="""<b>The selected combination of conditions was not tested in the manuscript, 
please see experimental design and select an alternative view.</b>""",visible = False, style={'color': 'red'})

#can we plot the data?
if len(data) == 0:
    #no..
    warning_experiment.visible = True
    #fix the default facets and get data again.
    w_facet.value = w_facet.options[0][0]
    w_facet2.value = w_facet2.options[1][0]
    data,data_no_dups = get_data()

#Plotting#
source = ColumnDataSource(data)
source_no_dups = ColumnDataSource(data_no_dups)
table = DataTable(source=source_no_dups,
                  margin=10,
                  index_position=None,
                  sizing_mode = "fixed",
                  width = 500,
                  columns=[
                      TableColumn(field='cat_value', title='Category'),
                      TableColumn(field='count', title='No Samples/Cells',
                                  formatter=ScientificFormatter(precision=0)),
                      TableColumn(field='perc', title='% Samples/Cells',
                                  formatter=ScientificFormatter(precision=1)),
                      TableColumn(field='mean', title='Mean',
                                  formatter=ScientificFormatter(precision=2)),
                      TableColumn(field='median', title='Median',
                                  formatter=ScientificFormatter(precision=2)),
                      TableColumn(field='q01', title='1% Quantile',
                                  formatter=ScientificFormatter(precision=2)),
                      TableColumn(field='q25', title='20% Quantile',
                                  formatter=ScientificFormatter(precision=2)),
                      TableColumn(field='q75', title='80% Quantile',
                                  formatter=ScientificFormatter(precision=2)),
                      TableColumn(field='q99', title='99% Quantile',
                                  formatter=ScientificFormatter(precision=2)),
                  ])

# meta3 = w_facet3.value
# meta3 = w_facet3.value
mapper = get_mapper()

# create plot elements - these are the same for boxplots as mean/std type plots


elements = dict(
    vbar=plot.vbar(x="cat_value", top='_bar_top',
                bottom='_bar_bottom', source = source, width=0.85, name="barplot",
                fill_color={'field': coloring_scheme, 'transform': mapper},
                line_color="black"),
    seg_v_up=plot.segment(source=source, x0='cat_value', x1='cat_value',
                          y0='_bar_top', y1='_segment_top',
                          line_color='black'),
    seg_h_up=plot.rect(source=source, x='cat_value', height=0.001,
                       y='_segment_top', width=0.4, line_color='black'),
    seg_v_dw=plot.segment(source=source, x0='cat_value', x1='cat_value',
                          y0='_segment_bottom', y1='_bar_bottom',
                          line_color='black'),
    seg_h_dw=plot.rect(source=source, x='cat_value', height=0.001,
                       y='_segment_bottom', width=0.4, line_color='black'),
    seg_h_med=plot.rect(source=source, x='cat_value', height=0.001,
                        y='_bar_median', width=0.85, line_width=2,
                        line_color='black'),
    # jitter_points = plot.scatter(x=jitter('cat_value', width=0.4, range=plot.x_range), y=f'mean_{meta3}', size=5, alpha=0.4, source=source,legend_label = f"{meta3}")
    jitter_points = plot.scatter(x=jitter('cat_value', width=0.4, range=plot.x_range), y="jitter", size=5, alpha=0.4, source=source)

)

#to orient the legends of the x axis
X_AXIS_LABELS_ORIENTATION = 3.14/2
plot.xaxis.group_label_orientation = X_AXIS_LABELS_ORIENTATION
plot.xaxis.major_label_orientation = X_AXIS_LABELS_ORIENTATION

yspacer = (data['_segment_top'].max() - data['_segment_bottom'].min()) / 20

ymax = data['_segment_top'].max() + yspacer
ymin = data['_segment_bottom'].min() - yspacer
plot.update(y_range=Range1d(ymin, ymax))

citation = Div(text=f'{expset.get_legend_of_obs(w_dataset_id.value,w_facet.value)}')

#check for metadata order
ordered_list = get_order()
order = {key: i for i, key in enumerate(ordered_list)}

if order and w_facet2.value != "--":
    plot.x_range.factors = sorted(list(set(data["cat_value"])),key = lambda d: (d[0],order[d[1]]))
else:
    plot.x_range.factors = sorted(list(set(data["cat_value"])),key=lambda tup: tup[0])

plot.xaxis.group_label_orientation = X_AXIS_LABELS_ORIENTATION 
plot.xaxis.major_label_orientation = X_AXIS_LABELS_ORIENTATION
plot.xaxis.major_label_text_font_size = "10px"

def cb_update_plot(attr, old, new):
    """Populate and update the plot."""
    curdoc().hold()
    global plot, source, data, data_no_dups
    update_facets()
    #keeping old data and getting new data
    old_data = data
    old_data_no_dups = data_no_dups
    new_data,new_data_no_dups = get_data()

    dataset_id, dataset = get_dataset()
    facet = w_facet.value
    gene = w_gene.value

    #can we plot the new data?
    if len(new_data) == 0:
        #no..
        warning_experiment.visible = True
        data = old_data
        data_no_dups = old_data_no_dups
        #keep the old data.
    else:
        #yes, update everything.
        warning_experiment.visible = False
        data = new_data
        data_no_dups = new_data_no_dups
        source.data = data
        source_no_dups.data = data_no_dups

        #mapper for color, and mapper for order. if found.
        mapper = get_mapper()
        elements["vbar"].glyph.fill_color = {'field': coloring_scheme, 'transform': mapper}
        ordered_list = get_order()
        order = {key: i for i, key in enumerate(ordered_list)}
        if order and w_facet2.value != "--":
            plot.x_range.factors = sorted(list(set(data["cat_value"])),key = lambda d:  (d[0],order[d[1]]))
        else:
            plot.x_range.factors = sorted(list(set(data["cat_value"])),key=lambda tup: tup[0])

    w_div_title_author.text = \
        f"""
        <ul>
          <li><b>Title:</b> {dataset['title']}</li>
          <li><b>Author:</b> {dataset['author']}</li>
          <li><b>Organism / Datatype:</b>
              {dataset['organism']} / {dataset['datatype']}</li>
        </ul>
        """

    w_download_filename.text = f"exp_{dataset_id}_{facet}_{gene}.tsv"

    # plan for 5% space above & below
    yspacer = (data['_segment_top'].max() - data['_segment_bottom'].min()) / 20

    ymax = data['_segment_top'].max() + yspacer
    ymin = data['_segment_bottom'].min() - yspacer

    #fixing y range min max    
    plot.y_range.update(start=ymin, end=ymax)

    #title of plot
    title = dataset['short_title']
    if len(title) > 80:
        title = title[:77] + '...'
    plot.title.text = (f"Boxplot of {gene} vs {facet}"
                       f" - {dataset['organism']}"
                       f" - {dataset['first_author']} - {title}")

    ##x-axis legend
    plot.yaxis.axis_label = f"{dataset['datatype']}"

    #adding citation if found.
    citation.text = f'{expset.get_legend_of_obs(dataset_id,facet)}'
    curdoc().unhold()


# convenience shortcut
update_plot = partial(cb_update_plot, attr=None, old=None, new=None)

# run it directly to ensure there are initial values
update_plot()


def cb_dataset_change(attr, old, new):
    """Dataset change."""
    lg.info("Dataset Change to:" + new)
    w_dataset_id.value = new
    update_facets()
    update_genes()
    update_sibling_options()
    update_plot()

def cb_sibling_change(attr, old, new):
    lg.debug("Sibling change: " + new)
    w_dataset_id.value = new
    update_facets()
    update_genes()
    update_plot()

cb_download = CustomJS(
    args=dict(data=source.data,
              columns=[x for x in source.data.keys() if not x.startswith('_')],
              filename_div=w_download_filename),
    code="exportToTsv(data, columns, filename_div.text);")

w_gene.on_change("value", cb_update_plot)
w_sibling.on_change("value", cb_sibling_change)
w_dataset_id.on_change("value", cb_dataset_change)
w_facet.on_change("value", cb_update_plot)
w_facet2.on_change("value",cb_update_plot)
w_download.js_on_click(cb_download)
w_facet3.on_change("value",cb_update_plot)

#
# Build the document
#

curdoc().add_root(row([
    column([
        column([
        row([w_gene, w_facet,w_facet2],sizing_mode='scale_both'),
        row([w_facet3,w_sibling, w_download],sizing_mode='scale_both'),
        ]),
        column([w_div_title_author], sizing_mode='fixed'),
        column([w_dataset_id],sizing_mode='fixed'),
        column([warning_experiment],sizing_mode='scale_both'),
        column([table],sizing_mode='fixed')
        ]),
    column([
        column([plot], sizing_mode='scale_both'),
        column([citation], sizing_mode='scale_both'),

    ])
], sizing_mode='scale_both')
)