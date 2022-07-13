"""helpers for the gene expression app."""

import logging
import copy
import os
import time
from pathlib import Path
from pprint import pprint
import shutil

import typer
from typer import echo
from typing import List, Optional, Dict
import yaml

from beehive import util, expset

app = typer.Typer()

lg = logging.getLogger(__name__)


def value_typer(key, val):
    """Convert values to the correct datatype - if necessary"""
    if key in ['year']:
        return int(val)
    return val


def check_yaml(dataset_id, data, **defaults):
    """Check YAML & fixes it where possible"""

    import pandas as pd
    incoming_uid = util.make_hash_sha256(data)
    mandatory_fields = '''
        author title datatype organism short_title study year
        '''.split()
    optional_fields = '''
        description '''.split()

    problems = []
    warnings = []
    messages = []

    for mf in mandatory_fields:
        if mf not in data:
            if mf in defaults:
                data[mf] = defaults[mf]
            else:
                problems.append(f"Missing field: {mf}")
    for of in optional_fields:
        if of not in data:
            if of in defaults:
                data[of] = defaults[of]
                changed=True
            else:
                warnings.append(f"Missing optional field: {mf}")
    
    if not isinstance(data['year'], int):
        problems.append("Year is not an integer: " + str(data['year']))

    if data['organism'] not in ['human', 'mouse', 'human+mouse']:
        problems.append("Unexpected organism: " + data['organism'])

    obsfields = expset.get_obsfields(dataset_id)
    if not 'obs_meta' in data:
        data['obs_meta'] = {}

    obm = data['obs_meta']

    for k in obsfields:
        if not k in obm:
            obm[k] = dict(name=k)     
        elif isinstance(obm[k], str):
            # fix emma's initial format
            obm[k] = dict(name=obm[k])
        
        fields = pd.Series(expset.get_meta(dataset_id, k, raw=True)).iloc[0]
        varfields = expset.get_varfields(dataset_id)
        DE_fields = [x[:-5] for x in varfields if x.endswith('__lfc')]
        no_unique = len(fields.unique()) 

        odtype = obm[k].get('dtype')

        if fields.is_numeric():
            if odtype is not None:
                if odtype not in ['numerical', 'skip']:
                    warnings.append(f"Field{k} seems numeric, yet is assigned as {odtype} ")
            else:
                messages.append(f"Assigned field {k} as numerical")
                obm[k]['dtype'] = 'numerical'
                if no_unique < 15:
                    warnings.append(
                        f"Numerical field {k} has only {no_unique} unique values "  + 
                        "- should this be categorical?")
        else:
            if odtype is not None:
                if odtype not in ['categorical', 'skip']:
                    warnings.append(f"Field{k} seems categorical, yet is assigned as {odtype} ")
            else:
                messages.append(f"Assigned field {k} as categorical")                
                if no_unique > 20:
                    ff = ",".join(map(str, list(fields.unique())[:4]))
                    warnings.append(f"Field `{k}` appears categorical but has {no_unique}" +
                                    f" unique values - Skipping! - (first few:  {ff})")
                    obm[k]['dtype'] = 'skip'
                else:
                    obm[k]['dtype'] = 'categorical'

            if no_unique <= 20 and not 'values' in obm[k]:
                # metadata per possible value type:                                    
                values = {a: dict(name=str(a)) 
                        for a in sorted(fields.unique()) }

                for vk, vv in values.items():
                    dekey = f"{k}__{vk}"
                    if dekey in DE_fields:
                        vv['DE_prefix'] = dekey    
                obm[k]['values'] = values

    outgoing_uid = util.make_hash_sha256(data)
    return incoming_uid != outgoing_uid, problems, warnings, messages


@app.command("yaml-check")
def data_check(yaml_file: Path = typer.Argument(..., exists=True),
               defaults: List[str] = typer.Argument(None)):

    dataset_id = str(yaml_file.name).replace('.yaml', '')
    lg.info(f"processing dataset {dataset_id}")

    defaults_dict = {}
    for d in defaults:
        if not '=' in d:
            print(f"invalid default: {d}")
            exit(-1)

        k, v = d.split('=', 1)
        defaults_dict[k] = value_typer(k, v) 

    with open(yaml_file) as F:
        yml = yaml.load(F, Loader=yaml.SafeLoader)
    
    changed, problems, warnings, messages \
        = check_yaml(dataset_id, yml, **defaults_dict)

    if len(problems) == 0:
        print("No problems found")
    else:
        for p in problems:
            lg.error(f"PROBLEM: {p}")
        exit(0)

    for w in warnings:
        lg.warning(f"Warning: {w}")

    for m in messages:
        lg.debug(f"Message: {m}")

    if changed:
        i = 0
        while (backup_file := yaml_file.with_suffix(f".yaml-backup-{i:03d}")).exists():
            i += 1
        lg.warning(f"yaml changed - saving to {yaml_file}")
        lg.warning(f"old yaml file backed up to {backup_file}")        
        shutil.move(yaml_file, backup_file)
        with open(yaml_file, 'w') as F:
             yaml.dump(yml, F, Dumper=yaml.SafeDumper)
    else:
        lg.info("Yaml file did not change - not updating")



# @app.command("del")
# def h5ad_del(h5ad_file: Path = typer.Argument(..., exists=True),
#              key: str = typer.Argument(...)):

#     import scanpy as sc
#     lg.warning(f"Changing on {h5ad_file}")
#     lg.warning(f'Removing "{key}" from `.uns["study_md"]`')
#     adata = sc.read_h5ad(h5ad_file, backed='r+')
#     del adata.uns['study_md'][key]
#     adata.write()


# @ app.command("prepare")
# def h5ad_convert(h5ad_file: Path = typer.Argument(..., exists=True),
#                  author: str = None,
#                  title: str = None,
#                  ):
#     """Convert to polars/parquet dataframes."""

#     import scanpy as sc
#     import polars as pl
#     import pandas as pd

#     outbase = h5ad_file
#     lg.info(f"Filename for IO: {outbase}")

#     adata = sc.read_h5ad(h5ad_file)

#     # automatically fails if not exist
#     study_md = adata.uns['study_md']

#     for field in ['author', 'title', 'study', 'organism', 'datatype',
#                   'short_title', 'year']:
#         assert field in study_md

#     study_md['year'] = int(study_md['year'])

#     try:
#         adata.raw.to_adata()
#         lg.warning("Adata has a `.raw`! Are you sure you have the correct")
#         lg.warning("data in .X?")
#     except:  # NOQA: E722
#         pass

#     dfx = adata.to_df()

#     obs = adata.obs
#     var = adata.var
#     var.index = adata.var_names
#     var.index.name = 'gene'

#     study_md['meta'] = {}
#     study_md['diffexp'] = {}
#     study_md['dimred'] = []

#     keep = []
#     for k in var:
#         if (k.endswith('__lfc') or k.endswith('__padj')):
#             lg.info(f"Processing var {k}")
#             keep.append(k)

#     var = var[keep].copy()

#     for k, v in var.iteritems():
#         if not k.endswith('__padj'):
#             continue

#         kgroup, kkey, _ = k.rsplit('__', 2)
#         if kgroup not in study_md['diffexp']:
#             study_md['diffexp'][kgroup] = dict(keys=[kkey])
#         else:
#             study_md['diffexp'][kgroup]['keys'].append(kkey)

#         vv = v.sort_values().head(8)
#         topgenes = list(vv.index)
#         study_md['diffexp'][kgroup]['topgenes'] = topgenes

#     for k, v in obs.iteritems():
#         dtype = 'numerical'

#         # polars/parquest does not like categories
#         if str(v.dtype) == 'category':
#             obs[k] = v.astype('str')
#             dtype = 'categorical'

#         study_md['meta'][k] = dict(dtype=dtype)

#     obsms = []
#     for k in adata.obsm_keys():
#         if k.startswith('_'):
#             continue
#         study_md['dimred'].append(k)

#         oo = pd.DataFrame(adata.obsm[k], index=obs.index)
#         oo.columns = '_' + k + '_' + oo.columns.astype(str)
#         obsms.append(oo)

#     obs = pd.concat([obs] + obsms, axis=1)

#     obs.index.name = '_cell'
#     obs = obs.reset_index()

#     var = var.T
#     var.index.name = 'field'
#     var = var.reset_index()

#     lg.info("Writing output files to:")
#     lg.info(" - " + str(outbase.with_suffix('.obs.prq')))
#     pl.DataFrame(obs).write_parquet(outbase.with_suffix('.obs.prq'))
#     lg.info(" - " + str(outbase.with_suffix('.var.prq')))
#     pl.DataFrame(var).write_parquet(outbase.with_suffix('.var.prq'))
#     lg.info(" - " + str(outbase.with_suffix('.X.prq')))
#     pl.DataFrame(dfx).write_parquet(outbase.with_suffix('.X.prq'))

#     lg.info(" - " + str(outbase.with_suffix('.yaml')))
#     with open(outbase.with_suffix('.yaml'), 'w') as F:
#         yaml.dump(study_md, F, Dumper=yaml.SafeDumper)