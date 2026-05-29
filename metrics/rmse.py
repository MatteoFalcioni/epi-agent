#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May 15 14:30:00 2026

@author: Giulio Colombini
"""

import numpy as np

# Metric attributes

name = 'rmse'

# Root Mean Square Error

def metric(x, t_span, model, args, data):
    # x = model parameters which we want to fit.
    # t_span = fitting interval
    # model = callable model(t_span, x, args) providing a prediction.
    # args  = fixed parameters.
    # data = fit data to use to compute the metric.

    assert len(data) == t_span[1] - t_span[0],'Shape mismatch between data and t_span.'

    cur_pred_incidence = model(x, t_span, *args)

    gap = cur_pred_incidence - data

    return np.sqrt((gap*gap).sum()/len(gap))
