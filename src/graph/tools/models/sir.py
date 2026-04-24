#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 3 14:30:19 2026

@author: Giulio Colombini
"""

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from scipy.integrate import solve_ivp
from scipy.optimize import minimize


def sir(t, y, beta, mu, N):
    return np.array([- beta * y[0] * y[1] / N, 
                       beta * y[0] * y[1] / N - mu * y[1],
                       mu * y[1]])

def sir_incidence(x, t_span, N):
    beta, mu, I0, f = x # Respectively beta = infectivity, 
                        #              mu = recovery rate, 
                        #              I0 = initial infective people,
                        #              f = detection fraction.

    y0 = np.array([N-I0, I0, 0.])

    sol = solve_ivp(sir, t_span = (t_span), y0 = y0,
                    args = (beta, mu, N), 
                    t_eval = np.arange(*t_span, 1.),
                    method = 'Radau')
    s, i, r = sol.y

    incidence = f * beta * s * i / N

    return incidence

def rmse(x, t_span, model, args, data):
    # x = model parameters which we want to fit.
    # t_span = fitting interval
    # model = callable model(t_span, x, args) providing a prediction.
    # data = fit data to use to compute the metric.

    assert len(data) == t_span[1] - t_span[0],'Shape mismatch between data and t_span.'

    cur_pred_incidence = model(x, t_span, *args)

    gap = cur_pred_incidence - data

    return np.sqrt((gap*gap).sum()/len(gap))

def fit(model, objf, data, initial_guess, fixed_args, verbose = True):
    optimum = minimize(objf, x0 = initial_guess,
                             args = ((0., len(data)), model, 
                                     fixed_args, data),
                             bounds = ((0., np.inf), (0., np.inf), (0., np.inf),
                                       (0., np.inf)))
    if verbose:
        print(optimum)
    return optimum

if __name__ == '__main__':

    N = 886891  # total population (example)
    
    df = pd.read_csv('daily_positives_flu.csv', index_col = 0, parse_dates = True)
    
    beg     = '2025-11-01'
    end_fit = '2025-12-31'
    end_tst = '2026-02-28'
    
    df['0'].plot(color = 'C1')
    df['0'].rolling(7, min_periods = 1, center = False).mean().plot(color = 'C0')
    
    plt.vlines([beg, end_fit, end_tst], ymin = 0., ymax = 50, linestyle = 'dashed',
               color = 'red')
    
    plt.show()
    
    df_fit = df[(df.index >= beg) & (df.index <= end_fit)]
    fit_index = df_fit.index
    df_tst = df[(df.index >= beg) & (df.index <= end_tst)]
    tst_index = df_tst.index
    
    fit_incidence = df_fit['0'].rolling(7, min_periods = 1, 
                                        center = False).mean().to_numpy()
    tst_incidence = df_tst['0'].rolling(7, min_periods = 1, 
                                        center = False).mean().to_numpy()

    initial_guess = np.array([1., 0.2, fit_incidence[0]/0.1, 0.1])
    
    optimum = fit(sir_incidence, rmse, fit_incidence, 
                  initial_guess = initial_guess, fixed_args = (N,), verbose = True)
    
    obeta, omu, oI0, of = optimum.x 
    
    print("R0 =", obeta/omu)
    
    t_span = (0, len(tst_incidence))
    
    sol_opt = solve_ivp(sir, t_span = t_span, 
                        y0 = np.array([N - oI0, oI0, 0.]),
                        args = (obeta, omu, N), 
                        t_eval = np.arange(*t_span, 1.),
                        method = 'Radau')
    
    s, i, r = sol_opt.y
    
    pred_incidence = of * obeta * s * i / N
    
    fig, ax = plt.subplots()
    
    ax.plot(tst_index, tst_incidence) 
    ax.plot(tst_index, pred_incidence) 
    ax.vlines([end_fit], ymin = 0., ymax = 50, linestyle = 'dashed',
               color = 'C1')
    
    plt.show()
