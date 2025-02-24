import dataclasses
from dataclasses import dataclass
from typing import Dict
from typing import List
from typing import Optional


import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error
from sklearn.metrics import mean_absolute_percentage_error
from sklearn.metrics import mean_squared_error
from sklearn.metrics import r2_score

from evidently.calculations.regression_performance import calculate_regression_performance
from evidently.metrics.base_metric import InputData
from evidently.metrics.base_metric import Metric
from evidently.metrics.utils import make_target_bins_for_reg_plots
from evidently.metrics.utils import make_hist_for_cat_plot
from evidently.metrics.utils import apply_func_to_binned_data
from evidently.metrics.utils import make_hist_for_num_plot
from evidently.model.widget import BaseWidgetInfo
from evidently.renderers.base_renderer import default_renderer
from evidently.renderers.base_renderer import MetricHtmlInfo
from evidently.renderers.base_renderer import MetricRenderer
from evidently.utils.data_operations import process_columns
from evidently.utils.data_operations import DatasetColumns


@dataclass
class RegressionPerformanceMetricsResults:
    columns: DatasetColumns
    r2_score: float
    rmse: float
    rmse_default: float
    mean_error: float
    me_default_sigma: float
    me_hist_for_plot: Dict[str, pd.Series]
    mean_abs_error: float
    mean_abs_error_default: float
    mean_abs_perc_error: float
    mean_abs_perc_error_default: float
    abs_error_max: float
    abs_error_max_default: float
    error_std: float
    abs_error_std: float
    abs_perc_error_std: float
    error_normality: dict
    underperformance: dict
    hist_for_plot: Dict[str, pd.Series]
    vals_for_plots: Dict[str, Dict[str, pd.Series]]
    error_bias: Optional[dict] = None
    mean_error_ref: Optional[float] = None
    mean_abs_error_ref: Optional[float] = None
    mean_abs_perc_error_ref: Optional[float] = None
    rmse_ref: Optional[float] = None
    r2_score_ref: Optional[float] = None
    abs_error_max_ref: Optional[float] = None
    underperformance_ref: Optional[dict] = None


class RegressionPerformanceMetrics(Metric[RegressionPerformanceMetricsResults]):
    def get_parameters(self) -> tuple:
        return ()

    def calculate(self, data: InputData) -> RegressionPerformanceMetricsResults:
        columns = process_columns(data.current_data, data.column_mapping)

        current_metrics = calculate_regression_performance(
            dataset=data.current_data, columns=columns, error_bias_prefix="current_"
        )
        error_bias = current_metrics.error_bias
        reference_metrics = None

        if data.reference_data is not None:
            ref_columns = process_columns(data.reference_data, data.column_mapping)
            reference_metrics = calculate_regression_performance(
                dataset=data.reference_data, columns=ref_columns, error_bias_prefix="ref_"
            )

            if reference_metrics is not None and reference_metrics.error_bias:
                for feature_name, current_bias in reference_metrics.error_bias.items():
                    if feature_name in error_bias:
                        error_bias[feature_name].update(current_bias)

                    else:
                        error_bias[feature_name] = current_bias

        r2_score_value = r2_score(
            y_true=data.current_data[data.column_mapping.target],
            y_pred=data.current_data[data.column_mapping.prediction],
        )
        rmse_score_value = mean_squared_error(
            y_true=data.current_data[data.column_mapping.target],
            y_pred=data.current_data[data.column_mapping.prediction],
        )

        # mae default values
        dummy_preds = data.current_data[data.column_mapping.target].median()
        mean_abs_error_default = mean_absolute_error(
            y_true=data.current_data[data.column_mapping.target], y_pred=[dummy_preds] * data.current_data.shape[0]
        )
        # rmse default values
        rmse_ref = None
        if data.reference_data is not None:
            rmse_ref = mean_squared_error(
                y_true=data.reference_data[data.column_mapping.target],
                y_pred=data.reference_data[data.column_mapping.prediction],
            )
        dummy_preds = data.current_data[data.column_mapping.target].mean()
        rmse_default = mean_squared_error(
            y_true=data.current_data[data.column_mapping.target], y_pred=[dummy_preds] * data.current_data.shape[0]
        )
        # mape default values
        # optimal constant for mape
        s = data.current_data[data.column_mapping.target]
        inv_y = 1 / s[s != 0].values
        w = inv_y / sum(inv_y)
        idxs = np.argsort(w)
        sorted_w = w[idxs]
        sorted_w_cumsum = np.cumsum(sorted_w)
        idx = np.where(sorted_w_cumsum > 0.5)[0][0]
        pos = idxs[idx]
        dummy_preds = s[s != 0].values[pos]

        mean_abs_perc_error_default = (
            mean_absolute_percentage_error(
                y_true=data.current_data[data.column_mapping.target], y_pred=[dummy_preds] * data.current_data.shape[0]
            )
            * 100
        )
        #  r2_score default values
        r2_score_ref = None
        if data.reference_data is not None:
            r2_score_ref = r2_score(
                y_true=data.reference_data[data.column_mapping.target],
                y_pred=data.reference_data[data.column_mapping.prediction],
            )
        # max error default values
        abs_error_max_ref = None
        mean_error_ref = None

        if reference_metrics is not None:
            abs_error_max_ref = reference_metrics.abs_error_max
            mean_error_ref = reference_metrics.mean_error

        y_true = data.current_data[data.column_mapping.target]
        y_pred = data.current_data[data.column_mapping.prediction]
        abs_error_max_default = np.abs(y_true - y_true.median()).max()

        #  me default values
        me_default_sigma = (y_pred - y_true).std()

        # visualisation

        df_target_binned = make_target_bins_for_reg_plots(
            data.current_data, data.column_mapping.target, data.column_mapping.prediction, data.reference_data
        )
        curr_target_bins = df_target_binned.loc[df_target_binned.data == "curr", "target_binned"]
        ref_target_bins = None
        if data.reference_data is not None:
            ref_target_bins = df_target_binned.loc[df_target_binned.data == "ref", "target_binned"]
        hist_for_plot = make_hist_for_cat_plot(curr_target_bins, ref_target_bins)

        vals_for_plots = {}

        if data.reference_data is not None:
            is_ref_data = True

        else:
            is_ref_data = False

        for name, func in zip(
            ["r2_score", "rmse", "mean_abs_error", "mean_abs_perc_error"],
            [r2_score, mean_squared_error, mean_absolute_error, mean_absolute_percentage_error],
        ):
            vals_for_plots[name] = apply_func_to_binned_data(
                df_target_binned, func, data.column_mapping.target, data.column_mapping.prediction, is_ref_data
            )

        # me plot
        err_curr = data.current_data[data.column_mapping.prediction] - data.current_data[data.column_mapping.target]
        err_ref = None

        if is_ref_data:
            err_ref = (
                data.reference_data[data.column_mapping.prediction] - data.reference_data[data.column_mapping.target]
            )
        me_hist_for_plot = make_hist_for_num_plot(err_curr, err_ref)

        if r2_score_ref is not None:
            r2_score_ref = float(r2_score_ref)

        if rmse_ref is not None:
            rmse_ref = float(rmse_ref)

        underperformance_ref = None

        if reference_metrics is not None:
            underperformance_ref = reference_metrics.underperformance

        return RegressionPerformanceMetricsResults(
            columns=columns,
            r2_score=r2_score_value,
            rmse=rmse_score_value,
            rmse_default=rmse_default,
            mean_error=current_metrics.mean_error,
            mean_error_ref=mean_error_ref,
            me_default_sigma=me_default_sigma,
            me_hist_for_plot=me_hist_for_plot,
            mean_abs_error=current_metrics.mean_abs_error,
            mean_abs_error_default=mean_abs_error_default,
            mean_abs_perc_error=current_metrics.mean_abs_perc_error,
            mean_abs_perc_error_default=mean_abs_perc_error_default,
            abs_error_max=current_metrics.abs_error_max,
            abs_error_max_default=abs_error_max_default,
            error_std=current_metrics.error_std,
            abs_error_std=current_metrics.abs_error_std,
            abs_perc_error_std=current_metrics.abs_perc_error_std,
            error_normality=current_metrics.error_normality,
            underperformance=current_metrics.underperformance,
            underperformance_ref=underperformance_ref,
            hist_for_plot=hist_for_plot,
            vals_for_plots=vals_for_plots,
            error_bias=error_bias,
            mean_abs_error_ref=reference_metrics.mean_abs_error if reference_metrics is not None else None,
            mean_abs_perc_error_ref=reference_metrics.mean_abs_perc_error if reference_metrics is not None else None,
            rmse_ref=rmse_ref,
            r2_score_ref=r2_score_ref,
            abs_error_max_ref=abs_error_max_ref,
        )


@default_renderer(wrap_type=RegressionPerformanceMetrics)
class RegressionPerformanceMetricsRenderer(MetricRenderer):
    def render_json(self, obj: RegressionPerformanceMetrics) -> dict:
        result = dataclasses.asdict(obj.get_result())
        # remove values with DataFrames or Series
        result.pop("hist_for_plot")
        result.pop("vals_for_plots")
        result.pop("me_hist_for_plot")
        return result

    @staticmethod
    def _get_underperformance_tails(dataset_name: str, underperformance: dict) -> MetricHtmlInfo:
        return MetricHtmlInfo(
            f"regression_performance_metrics_underperformance_{dataset_name.lower()}",
            BaseWidgetInfo(
                title=f"{dataset_name.capitalize()}: Mean Error per Group (+/- std)",
                type="counter",
                size=2,
                params={
                    "counters": [
                        {"value": round(underperformance["majority"]["mean_error"], 2), "label": "Majority(90%)"},
                        {
                            "value": round(underperformance["underestimation"]["mean_error"], 2),
                            "label": "Underestimation(5%)",
                        },
                        {
                            "value": round(underperformance["overestimation"]["mean_error"], 2),
                            "label": "Overestimation(5%)",
                        },
                    ]
                },
            ),
            details=[],
        )

    def render_html(self, obj: RegressionPerformanceMetrics) -> List[MetricHtmlInfo]:
        metric_result = obj.get_result()
        target_name = metric_result.columns.utility_columns.target
        result = [
            MetricHtmlInfo(
                "regression_performance_title",
                BaseWidgetInfo(
                    type=BaseWidgetInfo.WIDGET_INFO_TYPE_COUNTER,
                    title="",
                    size=2,
                    params={
                        "counters": [{"value": "", "label": f"Regression Model Performance. Target: '{target_name}’"}]
                    },
                ),
                details=[],
            ),
            MetricHtmlInfo(
                "regression_performance_metrics_table_current",
                BaseWidgetInfo(
                    title="Current: Regression Performance Metrics",
                    type=BaseWidgetInfo.WIDGET_INFO_TYPE_COUNTER,
                    size=2,
                    params={
                        "counters": [
                            {"value": str(round(metric_result.mean_error, 3)), "label": "Mean error"},
                            {"value": str(round(metric_result.mean_abs_error, 3)), "label": "MAE"},
                            {"value": str(round(metric_result.mean_abs_perc_error, 3)), "label": "MAPE"},
                            {"value": str(round(metric_result.rmse, 3)), "label": "RMSE"},
                            {"value": str(round(metric_result.r2_score, 3)), "label": "r2 score"},
                        ]
                    },
                ),
                details=[],
            ),
        ]
        if (
            metric_result.mean_error_ref is not None
            and metric_result.mean_abs_error_ref is not None
            and metric_result.mean_abs_perc_error_ref is not None
            and metric_result.rmse_ref is not None
            and metric_result.r2_score_ref is not None
        ):
            result.append(
                MetricHtmlInfo(
                    "regression_performance_metrics_table_reference",
                    BaseWidgetInfo(
                        title="Reference: Regression Performance Metrics",
                        type=BaseWidgetInfo.WIDGET_INFO_TYPE_COUNTER,
                        size=2,
                        params={
                            "counters": [
                                {"value": str(round(metric_result.mean_error_ref, 3)), "label": "Mean error"},
                                {"value": str(round(metric_result.mean_abs_error_ref, 3)), "label": "MAE"},
                                {
                                    "value": str(round(metric_result.mean_abs_perc_error_ref, 3)),
                                    "label": "MAPE",
                                },
                                {"value": str(round(metric_result.rmse_ref, 3)), "label": "RMSE"},
                                {"value": str(round(metric_result.r2_score_ref, 3)), "label": "r2 score"},
                            ]
                        },
                    ),
                    details=[],
                )
            )

        result.append(
            self._get_underperformance_tails(dataset_name="current", underperformance=metric_result.underperformance)
        )

        if metric_result.underperformance_ref:
            result.append(
                self._get_underperformance_tails(
                    dataset_name="reference", underperformance=metric_result.underperformance_ref
                )
            )
        return result
