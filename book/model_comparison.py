from __future__ import division
import pylab as pl
import pandas
import sys
sys.path += ['.', '..', "/homes/peterhm/gbd/", "/homes/peterhm/gbd/book"] 

import dismod3
reload(dismod3)

import book_graphics
reload(book_graphics)

import model_utilities as mu
reload(mu)

rate_types = ['neg_binom']#, 'normal', 'log_normal_model', 'binom']
stats = ['bias', 'rmse', 'mae', 'mare', 'pc']
model_num = sys.argv[1]
data_type = 'p'

iter=10000
burn=1000
thin=5

output = pandas.DataFrame(pl.zeros((len(rate_types), len(stats))), index=rate_types, columns=stats)

for r in rate_types:
    model = mu.load_new_model(model_num)
    model, tester_ix, tester_data_type_ix = mu.tester_trainer(model, data_type)
    model = mu.create_new_vars(model, r, data_type, 'europe_western', 'male', 2005, iter, thin, burn)
    dismod3.fit.fit_asr(model, data_type, iter=iter, thin=thin, burn=burn)
    pred = model.vars[data_type]['p_pred'].stats()['mean'] 
    pred_ui = model.vars[data_type]['p_pred'].stats()['95% HPD interval']
    obs = model.vars[data_type]['p_obs'].value
    n = model.vars[data_type]['p_pred'].stats()['n']
    
    output.ix[r, 'bias'] = pl.mean(obs[tester_data_type_ix] - pred[tester_data_type_ix])
    output.ix[r, 'rmse'] = pl.sqrt(sum((obs[tester_data_type_ix] - pred[tester_data_type_ix])**2)/n)
    output.ix[r, 'mae'] = pl.median(abs(pred[tester_data_type_ix]-obs[tester_data_type_ix]))
    output.ix[r, 'mare'] = pl.median(((pred[tester_data_type_ix]-obs[tester_data_type_ix])/obs[tester_data_type_ix])*100)
    output.ix[r, 'pc'] = (100*list((pred[tester_data_type_ix] >= pred_ui[tester_data_type_ix,0]) & (pred[tester_data_type_ix] <= pred_ui[tester_data_type_ix,1])).count(1))/len(tester_data_type_ix)

output.to_csv('model_comparison' + str(model_num) + '.csv')   