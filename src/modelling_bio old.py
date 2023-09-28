import pymc as pm
import arviz as az

import numpy as np
from scipy.stats import norm, beta
from scipy.optimize import minimize
from pymc.variational.callbacks import CheckParametersConvergence
# from pymc.sampling_jax import sample_numpyro_nuts
# from pymc.sampling import jax
import pandas as pd

import seaborn as sns
import plotly.express as px
import matplotlib.pyplot as plt
import xarray as xr

from tqdm import tqdm
from operator import attrgetter

# import color palette
import sys
sys.path.append("..") 
# from src.general_imports import sns_colors

from src.utils import plot

CHAINS = 4
CORES = 1
# cores are set at 1 to allow to 
# avoid daemonic children in mp

SITE_PARAMETERS = {
    'eta_0':    'eta_0',
    'omega':    'omega',
    'p':        'meth_init',
    'N':        'system_size',
    'var_init': 'var_init'
}

def get_site_params():
    return list(SITE_PARAMETERS.values())
def bio_sites(amdata, return_MAP=False, return_trace=True, show_progress=False, init_nuts='auto', target_accept=0.8, cores=CORES):

    if show_progress: print(f'Modelling {amdata.shape[0]} bio_sites')
    ages = np.broadcast_to(amdata.var.age, shape=(amdata.shape[0], amdata.shape[1])).T
    coords = {'sites': amdata.obs.index.values,
            'participants': amdata.var.index.values}

    with pm.Model(coords=coords) as model:

        # condition on maximal initial standard deviation
        init_std_bound = 0.1

        # Define priors
        eta_0 = pm.Uniform("eta_0", lower=0, upper=1, dims='sites')
        omega = pm.HalfNormal("omega", sigma=0.02, dims='sites')
        p = pm.Uniform("meth_init", lower=0, upper=1, dims='sites')
        N = pm.Uniform('system_size', lower= 1, upper=2_000, dims='sites')
        var_init = pm.Uniform("var_init", lower=0,
                                          upper=2*np.power(init_std_bound*N,2),
                                          dims='sites')
        # Useful variables
        eta_1 = 1-eta_0
        
        # model mean and variance
        var_term_0 = eta_0*eta_1
        var_term_1 = (1-p)*np.power(eta_0,2) + p*np.power(eta_1,2)

        mean = eta_0 + np.exp(-omega*ages)*((p-1)*eta_0 + p*eta_1)
        # mean = bio_site_mean(ages, eta_0, omega, p)


        variance = (var_term_0/N 
                + np.exp(-omega*ages)*(var_term_1-var_term_0)/N 
                + np.exp(-2*omega*ages)*(var_init/np.power(N,2) - var_term_1/N)
            )

        # Beta function parameter boundaries
        sigma = np.sqrt(variance)
        # sigma = pm.math.minimum(sigma,  pm.math.sqrt(mean * (1 - mean)) - 0.0001)

        # Define likelihood
        likelihood = pm.Beta("m-values",
            mu = mean,
            sigma = sigma,
            dims=("participants", "sites"),
            observed = amdata.X.T)


        res = {}
        if return_MAP:
            res['map'] = pm.find_MAP(progressbar=show_progress)

        if return_trace:
            trace = pm.sample(1000, tune=1000, init=init_nuts,
                                     chains=CHAINS, cores=cores,
                                     progressbar=show_progress,
                                     target_accept=target_accept, 
                                     nuts_sampler='nutpie')

            pm.compute_log_likelihood(trace, progressbar=False)
            ppc = pm.sample_posterior_predictive(trace,
                    extend_inferencedata=True)
            res['trace'] = trace
    return res