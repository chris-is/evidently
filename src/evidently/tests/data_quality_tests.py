from abc import ABC
from typing import List, Dict
from typing import Optional
from typing import Union

import numpy as np

from evidently.utils.data_operations import DatasetColumns
from evidently.model.widget import BaseWidgetInfo
from evidently.metrics import DataQualityMetrics
from evidently.metrics import DataQualityStabilityMetrics
from evidently.metrics import DataQualityValueListMetrics
from evidently.metrics import DataQualityValueRangeMetrics
from evidently.metrics import DataQualityValueQuantileMetrics
from evidently.renderers.base_renderer import default_renderer
from evidently.renderers.base_renderer import TestRenderer
from evidently.renderers.base_renderer import TestHtmlInfo
from evidently.renderers.base_renderer import DetailsInfo
from evidently.renderers.render_utils import plot_distr
from evidently.metrics import DataQualityCorrelationMetrics
from evidently.tests.base_test import BaseCheckValueTest
from evidently.tests.base_test import GroupingTypes
from evidently.tests.base_test import GroupData
from evidently.tests.base_test import Test
from evidently.tests.base_test import BaseTestGenerator
from evidently.tests.base_test import TestResult
from evidently.tests.base_test import TestValueCondition
from evidently.tests.utils import approx
from evidently.utils.types import Numeric
from evidently.tests.utils import plot_check
from evidently.tests.utils import plot_metric_value
from evidently.tests.utils import plot_value_counts_tables
from evidently.tests.utils import plot_value_counts_tables_ref_curr
from evidently.tests.utils import plot_correlations


DATA_QUALITY_GROUP = GroupData("data_quality", "Data Quality", "")
GroupingTypes.TestGroup.add_value(DATA_QUALITY_GROUP)


class BaseDataQualityMetricsValueTest(BaseCheckValueTest, ABC):
    group = DATA_QUALITY_GROUP.id
    metric: DataQualityMetrics

    def __init__(
        self,
        eq: Optional[Numeric] = None,
        gt: Optional[Numeric] = None,
        gte: Optional[Numeric] = None,
        is_in: Optional[List[Union[Numeric, str, bool]]] = None,
        lt: Optional[Numeric] = None,
        lte: Optional[Numeric] = None,
        not_eq: Optional[Numeric] = None,
        not_in: Optional[List[Union[Numeric, str, bool]]] = None,
        metric: Optional[DataQualityMetrics] = None,
    ):
        if metric is not None:
            self.metric = metric

        else:
            self.metric = DataQualityMetrics()

        super().__init__(eq=eq, gt=gt, gte=gte, is_in=is_in, lt=lt, lte=lte, not_eq=not_eq, not_in=not_in)


class TestConflictTarget(Test):
    group = DATA_QUALITY_GROUP.id
    name = "Test number of conflicts in target"
    metric: DataQualityStabilityMetrics

    def __init__(self, metric: Optional[DataQualityStabilityMetrics] = None):
        if metric is not None:
            self.metric = metric

        else:
            self.metric = DataQualityStabilityMetrics()

    def check(self):
        metric_result = self.metric.get_result()

        if metric_result.number_not_stable_target is None:
            test_result = TestResult.ERROR
            description = "No target in the dataset"

        elif metric_result.number_not_stable_target > 0:
            test_result = TestResult.FAIL
            description = f"Not stable target rows count is {metric_result.number_not_stable_target}"

        else:
            test_result = TestResult.SUCCESS
            description = "Target is stable"

        return TestResult(name=self.name, description=description, status=test_result)


class TestConflictPrediction(Test):
    group = DATA_QUALITY_GROUP.id
    name = "Test number of conflicts in prediction"
    metric: DataQualityStabilityMetrics

    def __init__(self, metric: Optional[DataQualityStabilityMetrics] = None):
        if metric is not None:
            self.metric = metric

        else:
            self.metric = DataQualityStabilityMetrics()

    def check(self):
        metric_result = self.metric.get_result()

        if metric_result.number_not_stable_prediction is None:
            test_result = TestResult.ERROR
            description = "No prediction in the dataset"

        elif metric_result.number_not_stable_prediction > 0:
            test_result = TestResult.FAIL
            description = f"Not stable prediction rows count is {metric_result.number_not_stable_prediction}"

        else:
            test_result = TestResult.SUCCESS
            description = "Prediction is stable"

        return TestResult(name=self.name, description=description, status=test_result)


class BaseDataQualityCorrelationsMetricsValueTest(BaseCheckValueTest, ABC):
    group = DATA_QUALITY_GROUP.id
    metric: DataQualityCorrelationMetrics
    method: str

    def __init__(
        self,
        method: str = "pearson",
        eq: Optional[Numeric] = None,
        gt: Optional[Numeric] = None,
        gte: Optional[Numeric] = None,
        is_in: Optional[List[Union[Numeric, str, bool]]] = None,
        lt: Optional[Numeric] = None,
        lte: Optional[Numeric] = None,
        not_eq: Optional[Numeric] = None,
        not_in: Optional[List[Union[Numeric, str, bool]]] = None,
        metric: Optional[DataQualityCorrelationMetrics] = None,
    ):
        self.method = method
        if metric is not None:
            self.metric = metric

        else:
            self.metric = DataQualityCorrelationMetrics(method=method)

        super().__init__(eq=eq, gt=gt, gte=gte, is_in=is_in, lt=lt, lte=lte, not_eq=not_eq, not_in=not_in)


class TestTargetPredictionCorrelation(BaseDataQualityCorrelationsMetricsValueTest):
    name = "Correlation between Target and Prediction"

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition

        reference_correlation = self.metric.get_result().reference
        if reference_correlation is not None and reference_correlation.target_prediction_correlation is not None:
            value = reference_correlation.target_prediction_correlation
            return TestValueCondition(eq=approx(value, absolute=0.25))

        return TestValueCondition(gt=0)

    def calculate_value_for_test(self) -> Optional[Numeric]:
        return self.metric.get_result().current.target_prediction_correlation

    def get_description(self, value: Numeric) -> str:
        if value is None:
            return "No target or prediction in the dataset."
        return (
            f"The correlation between the target and prediction is {value:.3}. "
            f"The test threshold is {self.get_condition()}."
        )


class TestHighlyCorrelatedFeatures(BaseDataQualityCorrelationsMetricsValueTest):
    name = "Highly Correlated Features"

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition

        reference_correlation = self.metric.get_result().reference
        if reference_correlation is not None and reference_correlation.abs_max_num_features_correlation is not None:
            value = reference_correlation.abs_max_num_features_correlation
            return TestValueCondition(eq=approx(value, relative=0.1))

        return TestValueCondition(lt=0.9)

    def calculate_value_for_test(self) -> Optional[Numeric]:
        return self.metric.get_result().current.abs_max_num_features_correlation

    def get_description(self, value: Numeric) -> str:
        return f"The maximum correlation is {value:.3g}. The test threshold is {self.get_condition()}."


@default_renderer(wrap_type=TestHighlyCorrelatedFeatures)
class TestHighlyCorrelatedFeaturesRenderer(TestRenderer):
    def render_json(self, obj: TestHighlyCorrelatedFeatures) -> dict:
        base = super().render_json(obj)
        base["parameters"]["condition"] = obj.get_condition().as_dict()
        base["parameters"]["abs_max_num_features_correlation"] = np.round(obj.value, 3)
        return base

    def render_html(self, obj: TestHighlyCorrelatedFeatures) -> TestHtmlInfo:
        info = super().render_html(obj)
        num_features = obj.metric.get_result().current.num_features
        current_correlations = obj.metric.get_result().current.correlation_matrix[num_features]
        reference_correlation = obj.metric.get_result().reference

        if reference_correlation is not None:
            reference_correlations_matrix = reference_correlation.correlation_matrix[num_features]

        else:
            reference_correlations_matrix = None

        fig = plot_correlations(current_correlations, reference_correlations_matrix)
        fig_json = fig.to_plotly_json()
        info.details.append(
            DetailsInfo(
                id="HighlyCorrelatedFeatures",
                title="",
                info=BaseWidgetInfo(
                    title="",
                    size=2,
                    type="big_graph",
                    params={"data": fig_json["data"], "layout": fig_json["layout"]},
                ),
            )
        )
        return info


class TestTargetFeaturesCorrelations(BaseDataQualityCorrelationsMetricsValueTest):
    name = "Correlation between Target and Features"

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition

        reference_correlation = self.metric.get_result().reference

        if reference_correlation is not None and reference_correlation.abs_max_target_features_correlation is not None:
            value = reference_correlation.abs_max_target_features_correlation
            return TestValueCondition(eq=approx(value, relative=0.1))

        return TestValueCondition(lt=0.9)

    def calculate_value_for_test(self) -> Optional[Numeric]:
        return self.metric.get_result().current.abs_max_target_features_correlation

    def get_description(self, value: Numeric) -> str:
        if value is None:
            return "No target in the current dataset"

        else:
            return f"The maximum correlation is {value:.3g}. The test threshold is {self.get_condition()}."


@default_renderer(wrap_type=TestTargetFeaturesCorrelations)
class TestTargetFeaturesCorrelationsRenderer(TestRenderer):
    def render_json(self, obj: TestTargetFeaturesCorrelations) -> dict:
        base = super().render_json(obj)
        base["parameters"]["condition"] = obj.get_condition().as_dict()

        if obj.value is not None:
            abs_max_target_features_correlation = np.round(obj.value, 3)

        else:
            abs_max_target_features_correlation = obj.value

        base["parameters"]["abs_max_target_features_correlation"] = abs_max_target_features_correlation
        return base

    def render_html(self, obj: TestTargetFeaturesCorrelations) -> TestHtmlInfo:
        info = super().render_html(obj)
        current_correlations_matrix = obj.metric.get_result().current.correlation_matrix
        reference_correlation = obj.metric.get_result().reference

        if reference_correlation is not None:
            reference_correlations_matrix = reference_correlation.correlation_matrix

        else:
            reference_correlations_matrix = None

        fig = plot_correlations(current_correlations_matrix, reference_correlations_matrix)
        fig_json = fig.to_plotly_json()
        info.details.append(
            DetailsInfo(
                id="TestTargetFeaturesCorrelations",
                title="",
                info=BaseWidgetInfo(
                    title="",
                    size=2,
                    type="big_graph",
                    params={"data": fig_json["data"], "layout": fig_json["layout"]},
                ),
            )
        )
        return info


class TestPredictionFeaturesCorrelations(BaseDataQualityCorrelationsMetricsValueTest):
    name = "Correlation between Prediction and Features"

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition

        reference_correlation = self.metric.get_result().reference

        if (
            reference_correlation is not None
            and reference_correlation.abs_max_prediction_features_correlation is not None
        ):
            value = reference_correlation.abs_max_prediction_features_correlation
            return TestValueCondition(eq=approx(value, relative=0.1))

        return TestValueCondition(lt=0.9)

    def calculate_value_for_test(self) -> Optional[Numeric]:
        return self.metric.get_result().current.abs_max_prediction_features_correlation

    def get_description(self, value: Numeric) -> str:
        if value is None:
            return "No prediction in the current dataset"

        else:
            return f"The maximum correlation is {value:.3g}. The test threshold is {self.get_condition()}."


@default_renderer(wrap_type=TestPredictionFeaturesCorrelations)
class TestPredictionFeaturesCorrelationsRenderer(TestRenderer):
    def render_json(self, obj: TestPredictionFeaturesCorrelations) -> dict:
        base = super().render_json(obj)
        base["parameters"]["condition"] = obj.get_condition().as_dict()

        if obj.value is not None:
            abs_max_prediction_features_correlation = np.round(obj.value, 3)

        else:
            abs_max_prediction_features_correlation = obj.value

        base["parameters"]["abs_max_prediction_features_correlation"] = abs_max_prediction_features_correlation
        return base

    def render_html(self, obj: TestTargetFeaturesCorrelations) -> TestHtmlInfo:
        info = super().render_html(obj)
        current_correlations_matrix = obj.metric.get_result().current.correlation_matrix
        reference_correlation = obj.metric.get_result().reference

        if reference_correlation is not None:
            reference_correlations_matrix = reference_correlation.correlation_matrix

        else:
            reference_correlations_matrix = None

        fig = plot_correlations(current_correlations_matrix, reference_correlations_matrix)
        fig_json = fig.to_plotly_json()
        info.details.append(
            DetailsInfo(
                id="TestTargetFeaturesCorrelations",
                title="",
                info=BaseWidgetInfo(
                    title="",
                    size=2,
                    type="big_graph",
                    params={"data": fig_json["data"], "layout": fig_json["layout"]},
                ),
            )
        )
        return info


class TestCorrelationChanges(BaseDataQualityCorrelationsMetricsValueTest):
    group = DATA_QUALITY_GROUP.id
    name = "Change in Correlation"
    metric: DataQualityCorrelationMetrics
    corr_diff: float

    def __init__(
        self,
        corr_diff: float = 0.25,
        method: str = "pearson",
        eq: Optional[Numeric] = None,
        gt: Optional[Numeric] = None,
        gte: Optional[Numeric] = None,
        is_in: Optional[List[Union[Numeric, str, bool]]] = None,
        lt: Optional[Numeric] = None,
        lte: Optional[Numeric] = None,
        not_eq: Optional[Numeric] = None,
        not_in: Optional[List[Union[Numeric, str, bool]]] = None,
        metric: Optional[DataQualityCorrelationMetrics] = None,
    ):
        super().__init__(
            method=method,
            eq=eq,
            gt=gt,
            gte=gte,
            is_in=is_in,
            lt=lt,
            lte=lte,
            not_eq=not_eq,
            not_in=not_in,
            metric=metric,
        )
        self.corr_diff = corr_diff

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition

        return TestValueCondition(eq=0)

    def calculate_value_for_test(self) -> Optional[Numeric]:
        reference_correlation = self.metric.get_result().reference
        current_correlation = self.metric.get_result().current
        if reference_correlation is None:
            raise ValueError("Reference should be present")
        diff = reference_correlation.correlation_matrix - current_correlation.correlation_matrix
        return (diff.abs() > self.corr_diff).sum().sum() / 2

    def get_description(self, value: Numeric) -> str:
        return f"Number of correlation violations is {value:.3g}. The test threshold is {self.get_condition()}."


@default_renderer(wrap_type=TestCorrelationChanges)
class TestCorrelationChangesRenderer(TestRenderer):
    def render_html(self, obj: TestCorrelationChanges) -> TestHtmlInfo:
        info = super().render_html(obj)
        current_correlations_matrix = obj.metric.get_result().current.correlation_matrix
        reference_correlation = obj.metric.get_result().reference

        if reference_correlation is not None:
            reference_correlations_matrix = reference_correlation.correlation_matrix

        else:
            reference_correlations_matrix = None

        fig = plot_correlations(current_correlations_matrix, reference_correlations_matrix)
        fig_json = fig.to_plotly_json()
        info.details.append(
            DetailsInfo(
                id="TestTargetFeaturesCorrelations",
                title="",
                info=BaseWidgetInfo(
                    title="",
                    size=2,
                    type="big_graph",
                    params={"data": fig_json["data"], "layout": fig_json["layout"]},
                ),
            )
        )
        return info


class BaseFeatureDataQualityMetricsTest(BaseDataQualityMetricsValueTest, ABC):
    column_name: str

    def __init__(
        self,
        column_name: str,
        eq: Optional[Numeric] = None,
        gt: Optional[Numeric] = None,
        gte: Optional[Numeric] = None,
        is_in: Optional[List[Union[Numeric, str, bool]]] = None,
        lt: Optional[Numeric] = None,
        lte: Optional[Numeric] = None,
        not_eq: Optional[Numeric] = None,
        not_in: Optional[List[Union[Numeric, str, bool]]] = None,
        metric: Optional[DataQualityMetrics] = None,
    ):
        self.column_name = column_name
        super().__init__(
            eq=eq, gt=gt, gte=gte, is_in=is_in, lt=lt, lte=lte, not_eq=not_eq, not_in=not_in, metric=metric
        )

    def groups(self) -> Dict[str, str]:
        return {
            GroupingTypes.ByFeature.id: self.column_name,
        }

    def check(self):
        result = TestResult(name=self.name, description="The test was not launched", status=TestResult.SKIPPED)
        features_stats = self.metric.get_result().features_stats.get_all_features()

        if self.column_name not in features_stats:
            result.mark_as_fail(f"Feature '{self.column_name}' was not found")
            return result

        result = super().check()

        if self.value is None:
            result.mark_as_error(f"No value for the feature '{self.column_name}'")
            return result

        return result


class TestFeatureValueMin(BaseFeatureDataQualityMetricsTest):
    name = "Min Value"

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition

        ref_features_stats = self.metric.get_result().reference_features_stats

        if ref_features_stats is not None:
            min_value = ref_features_stats.get_all_features()[self.column_name].min
            if isinstance(min_value, str):
                raise ValueError(f"{self.column_name} should be numerical or bool")
            return TestValueCondition(gte=min_value)
        raise ValueError("Neither required test parameters nor reference data has been provided.")

    def calculate_value_for_test(self) -> Optional[Union[Numeric, bool]]:
        features_stats = self.metric.get_result().features_stats.get_all_features()
        min_value = features_stats[self.column_name].min
        if isinstance(min_value, str):
            raise ValueError(f"{self.column_name} should be numerical or bool")
        return min_value

    def get_description(self, value: Numeric) -> str:
        return f"The minimum value of the column **{self.column_name}** is {value} The test threshold is {self.get_condition()}."


@default_renderer(wrap_type=TestFeatureValueMin)
class TestFeatureValueMinRenderer(TestRenderer):
    def render_html(self, obj: TestFeatureValueMin) -> TestHtmlInfo:
        column_name = obj.column_name
        info = super().render_html(obj)
        curr_distr = obj.metric.get_result().distr_for_plots[column_name]["current"]
        ref_distr = None
        if "reference" in obj.metric.get_result().distr_for_plots[column_name].keys():
            ref_distr = obj.metric.get_result().distr_for_plots[column_name]["reference"]
        fig = plot_distr(curr_distr, ref_distr)
        fig = plot_check(fig, obj.get_condition())
        min_value = obj.metric.get_result().features_stats[column_name].min

        if min_value is not None:
            fig = plot_metric_value(fig, float(min_value), f"current {column_name} min value")

        fig_json = fig.to_plotly_json()
        info.details.append(
            DetailsInfo(
                id=f"min_{column_name}",
                title="",
                info=BaseWidgetInfo(
                    title="",
                    size=2,
                    type="big_graph",
                    params={"data": fig_json["data"], "layout": fig_json["layout"]},
                ),
            )
        )
        return info


class TestFeatureValueMax(BaseFeatureDataQualityMetricsTest):
    name = "Test a feature max value"

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition
        ref_features_stats = self.metric.get_result().reference_features_stats
        if ref_features_stats is not None:
            max_value = ref_features_stats.get_all_features()[self.column_name].max
            if isinstance(max_value, str):
                raise ValueError(f"{self.column_name} should be numerical or bool")
            return TestValueCondition(lte=max_value)
        raise ValueError("Neither required test parameters nor reference data has been provided.")

    def calculate_value_for_test(self) -> Optional[Union[Numeric, bool]]:
        features_stats = self.metric.get_result().features_stats.get_all_features()
        max_value = features_stats[self.column_name].max
        if isinstance(max_value, str):
            raise ValueError(f"{self.column_name} should be numerical or bool")
        return max_value

    def get_description(self, value: Numeric) -> str:
        return f"The maximum value of the column **{self.column_name}** is {value}. The test threshold is {self.get_condition()}."


@default_renderer(wrap_type=TestFeatureValueMax)
class TestFeatureValueMaxRenderer(TestRenderer):
    def render_html(self, obj: TestFeatureValueMax) -> TestHtmlInfo:
        column_name = obj.column_name
        info = super().render_html(obj)
        curr_distr = obj.metric.get_result().distr_for_plots[column_name]["current"]
        ref_distr = None
        if "reference" in obj.metric.get_result().distr_for_plots[column_name].keys():
            ref_distr = obj.metric.get_result().distr_for_plots[column_name]["reference"]
        fig = plot_distr(curr_distr, ref_distr)
        fig = plot_check(fig, obj.get_condition())

        max_value = obj.metric.get_result().features_stats[column_name].max

        if max_value is not None:
            fig = plot_metric_value(fig, float(max_value), f"current {column_name} max value")

        fig_json = fig.to_plotly_json()
        info.details.append(
            DetailsInfo(
                id=f"max_{column_name}",
                title="",
                info=BaseWidgetInfo(
                    title="",
                    size=2,
                    type="big_graph",
                    params={"data": fig_json["data"], "layout": fig_json["layout"]},
                ),
            )
        )
        return info


class TestFeatureValueMean(BaseFeatureDataQualityMetricsTest):
    name = "Mean Value"

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition
        ref_features_stats = self.metric.get_result().reference_features_stats
        if ref_features_stats is not None:
            return TestValueCondition(eq=approx(ref_features_stats.get_all_features()[self.column_name].mean, 0.1))
        raise ValueError("Neither required test parameters nor reference data has been provided.")

    def calculate_value_for_test(self) -> Optional[Numeric]:
        features_stats = self.metric.get_result().features_stats.get_all_features()
        return features_stats[self.column_name].mean

    def get_description(self, value: Numeric) -> str:
        return f"The mean value of the column **{self.column_name}** is {value:.3g}. The test threshold is {self.get_condition()}."


@default_renderer(wrap_type=TestFeatureValueMean)
class TestFeatureValueMeanRenderer(TestRenderer):
    def render_html(self, obj: TestFeatureValueMean) -> TestHtmlInfo:
        column_name = obj.column_name
        info = super().render_html(obj)
        curr_distr = obj.metric.get_result().distr_for_plots[column_name]["current"]
        ref_distr = None
        if "reference" in obj.metric.get_result().distr_for_plots[column_name].keys():
            ref_distr = obj.metric.get_result().distr_for_plots[column_name]["reference"]
        fig = plot_distr(curr_distr, ref_distr)
        fig = plot_check(fig, obj.get_condition())
        mean_value = obj.metric.get_result().features_stats[column_name].mean

        if mean_value is not None:
            fig = plot_metric_value(fig, mean_value, f"current {column_name} mean value")

        fig_json = fig.to_plotly_json()
        info.details.append(
            DetailsInfo(
                id=f"mean_{column_name}",
                title="",
                info=BaseWidgetInfo(
                    title="",
                    size=2,
                    type="big_graph",
                    params={"data": fig_json["data"], "layout": fig_json["layout"]},
                ),
            )
        )
        return info


class TestFeatureValueMedian(BaseFeatureDataQualityMetricsTest):
    name = "Median Value"

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition
        ref_features_stats = self.metric.get_result().reference_features_stats
        if ref_features_stats is not None:
            return TestValueCondition(
                eq=approx(ref_features_stats.get_all_features()[self.column_name].percentile_50, 0.1)
            )
        raise ValueError("Neither required test parameters nor reference data has been provided.")

    def calculate_value_for_test(self) -> Optional[Numeric]:
        features_stats = self.metric.get_result().features_stats.get_all_features()
        return features_stats[self.column_name].percentile_50

    def get_description(self, value: Numeric) -> str:
        return f"The median value of the column **{self.column_name}** is {value:.3g}. The test threshold is {self.get_condition()}."


@default_renderer(wrap_type=TestFeatureValueMedian)
class TestFeatureValueMedianRenderer(TestRenderer):
    def render_html(self, obj: TestFeatureValueMedian) -> TestHtmlInfo:
        column_name = obj.column_name
        info = super().render_html(obj)
        curr_distr = obj.metric.get_result().distr_for_plots[column_name]["current"]
        ref_distr = None

        if "reference" in obj.metric.get_result().distr_for_plots[column_name].keys():
            ref_distr = obj.metric.get_result().distr_for_plots[column_name]["reference"]

        fig = plot_distr(curr_distr, ref_distr)
        fig = plot_check(fig, obj.get_condition())
        percentile_50 = obj.metric.get_result().features_stats[column_name].percentile_50

        if percentile_50 is not None:
            fig = plot_metric_value(fig, percentile_50, f"current {column_name} median value")

        fig_json = fig.to_plotly_json()
        info.details.append(
            DetailsInfo(
                id=f"median_{column_name}",
                title="",
                info=BaseWidgetInfo(
                    title="",
                    size=2,
                    type="big_graph",
                    params={"data": fig_json["data"], "layout": fig_json["layout"]},
                ),
            )
        )
        return info


class TestFeatureValueStd(BaseFeatureDataQualityMetricsTest):
    name = "Standard Deviation (SD)"

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition
        ref_features_stats = self.metric.get_result().reference_features_stats
        if ref_features_stats is not None:
            return TestValueCondition(eq=approx(ref_features_stats.get_all_features()[self.column_name].std, 0.1))
        raise ValueError("Neither required test parameters nor reference data has been provided.")

    def calculate_value_for_test(self) -> Optional[Numeric]:
        features_stats = self.metric.get_result().features_stats.get_all_features()
        return features_stats[self.column_name].std

    def get_description(self, value: Numeric) -> str:
        return (
            f"The standard deviation of the column **{self.column_name}** is {value:.3g}. "
            f"The test threshold is {self.get_condition()}."
        )


@default_renderer(wrap_type=TestFeatureValueStd)
class TestFeatureValueStdRenderer(TestRenderer):
    def render_html(self, obj: TestFeatureValueStd) -> TestHtmlInfo:
        column_name = obj.column_name
        info = super().render_html(obj)
        curr_distr = obj.metric.get_result().distr_for_plots[column_name]["current"]
        ref_distr = None
        if "reference" in obj.metric.get_result().distr_for_plots[column_name].keys():
            ref_distr = obj.metric.get_result().distr_for_plots[column_name]["reference"]
        fig = plot_distr(curr_distr, ref_distr)

        fig_json = fig.to_plotly_json()
        info.details.append(
            DetailsInfo(
                id=f"std_{column_name}",
                title="",
                info=BaseWidgetInfo(
                    title="",
                    size=2,
                    type="big_graph",
                    params={"data": fig_json["data"], "layout": fig_json["layout"]},
                ),
            )
        )
        return info


class TestNumberOfUniqueValues(BaseFeatureDataQualityMetricsTest):
    name = "Number of Unique Values"

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition

        reference_features_stats = self.metric.get_result().reference_features_stats
        if reference_features_stats is not None:
            ref_features_stats = reference_features_stats.get_all_features()
            unique_count = ref_features_stats[self.column_name].unique_count
            return TestValueCondition(eq=approx(unique_count, relative=0.1))
        return TestValueCondition(gt=1)

    def calculate_value_for_test(self) -> Optional[Numeric]:
        features_stats = self.metric.get_result().features_stats.get_all_features()
        return features_stats[self.column_name].unique_count

    def get_description(self, value: Numeric) -> str:
        return (
            f"The number of the unique values in the column **{self.column_name}** is {value}. "
            f"The test threshold is {self.get_condition()}."
        )


@default_renderer(wrap_type=TestNumberOfUniqueValues)
class TestNumberOfUniqueValuesRenderer(TestRenderer):
    def render_html(self, obj: TestNumberOfUniqueValues) -> TestHtmlInfo:
        info = super().render_html(obj)
        column_name = obj.column_name
        curr_df = obj.metric.get_result().counts_of_values[column_name]["current"]
        ref_df = None
        if "reference" in obj.metric.get_result().counts_of_values[column_name].keys():
            ref_df = obj.metric.get_result().counts_of_values[column_name]["reference"]
        additional_plots = plot_value_counts_tables_ref_curr(column_name, curr_df, ref_df, "num_of_unique_vals")
        info.details = additional_plots
        return info


class TestUniqueValuesShare(BaseFeatureDataQualityMetricsTest):
    name = "Share of Unique Values"

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition

        reference_features_stats = self.metric.get_result().reference_features_stats
        if reference_features_stats is not None:
            ref_features_stats = reference_features_stats.get_all_features()
            unique_percentage = ref_features_stats[self.column_name].unique_percentage

            if unique_percentage is not None:
                return TestValueCondition(eq=approx(unique_percentage / 100.0, relative=0.1))

        raise ValueError("Neither required test parameters nor reference data has been provided.")

    def calculate_value_for_test(self) -> Optional[Numeric]:
        features_stats = self.metric.get_result().features_stats.get_all_features()
        unique_percentage = features_stats[self.column_name].unique_percentage

        if unique_percentage is None:
            return None

        return unique_percentage / 100.0

    def get_description(self, value: Numeric) -> str:
        return (
            f"The share of the unique values in the column **{self.column_name}** is {value:.3}. "
            f"The test threshold is {self.get_condition()}."
        )


@default_renderer(wrap_type=TestUniqueValuesShare)
class TestUniqueValuesShareRenderer(TestRenderer):
    def render_html(self, obj: TestUniqueValuesShare) -> TestHtmlInfo:
        info = super().render_html(obj)
        column_name = obj.column_name
        curr_df = obj.metric.get_result().counts_of_values[column_name]["current"]
        ref_df = None
        if "reference" in obj.metric.get_result().counts_of_values[column_name].keys():
            ref_df = obj.metric.get_result().counts_of_values[column_name]["reference"]
        additional_plots = plot_value_counts_tables_ref_curr(column_name, curr_df, ref_df, "unique_vals_sare")
        info.details = additional_plots
        return info


class TestMostCommonValueShare(BaseFeatureDataQualityMetricsTest):
    name = "Share of the Most Common Value"

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition

        reference_features_stats = self.metric.get_result().reference_features_stats
        if reference_features_stats is not None:
            ref_features_stats = reference_features_stats.get_all_features()
            most_common_value_percentage = ref_features_stats[self.column_name].most_common_value_percentage

            if most_common_value_percentage is not None:
                return TestValueCondition(eq=approx(most_common_value_percentage / 100.0, relative=0.1))

        return TestValueCondition(lt=0.8)

    def calculate_value_for_test(self) -> Optional[Numeric]:
        features_stats = self.metric.get_result().features_stats.get_all_features()
        most_common_value_percentage = features_stats[self.column_name].most_common_value_percentage

        if most_common_value_percentage is None:
            return None

        return most_common_value_percentage / 100.0

    def get_description(self, value: Numeric) -> str:
        most_common_value = self.metric.get_result().counts_of_values[self.column_name]["current"].iloc[0, 0]
        return (
            f"The most common value in the column **{self.column_name}** is {most_common_value}. "
            f"Its share is {value:.3g}. "
            f"The test threshold is {self.get_condition()}."
        )


@default_renderer(wrap_type=TestMostCommonValueShare)
class TestMostCommonValueShareRenderer(TestRenderer):
    def render_json(self, obj: TestMostCommonValueShare) -> dict:
        base = super().render_json(obj)
        base["parameters"]["condition"] = obj.get_condition().as_dict()
        base["parameters"]["column_name"] = obj.column_name
        base["parameters"]["share_most_common_value"] = obj.value
        return base

    def render_html(self, obj: TestMostCommonValueShare) -> TestHtmlInfo:
        info = super().render_html(obj)
        column_name = obj.column_name

        if column_name is None:
            raise ValueError("column_name should be present")

        curr_df = obj.metric.get_result().counts_of_values[column_name]["current"]
        ref_df = None
        if "reference" in obj.metric.get_result().counts_of_values[column_name].keys():
            ref_df = obj.metric.get_result().counts_of_values[column_name]["reference"]
        additional_plots = plot_value_counts_tables_ref_curr(column_name, curr_df, ref_df, "most_common_value_sare")
        info.details = additional_plots
        return info


class TestAllColumnsMostCommonValueShare(BaseTestGenerator):
    """Creates most common value share tests for each column in the dataset"""

    def generate_tests(self, columns_info: DatasetColumns) -> List[TestMostCommonValueShare]:
        return [TestMostCommonValueShare(column_name=name) for name in columns_info.get_all_columns_list()]


class TestMeanInNSigmas(Test):
    group = DATA_QUALITY_GROUP.id
    name = "Mean Value Stability"
    metric: DataQualityMetrics
    column_name: str
    n_sigmas: int

    def __init__(self, column_name: str, n_sigmas: int = 2, metric: Optional[DataQualityMetrics] = None):
        self.column_name = column_name
        self.n_sigmas = n_sigmas
        if metric is not None:
            self.metric = metric

        else:
            self.metric = DataQualityMetrics()

    def check(self):
        reference_feature_stats = self.metric.get_result().reference_features_stats
        features_stats = self.metric.get_result().features_stats

        if not reference_feature_stats:
            raise ValueError("Reference should be present")

        if self.column_name not in features_stats.get_all_features():
            description = f"Column {self.column_name} should be in current data"
            test_result = TestResult.ERROR

        elif self.column_name not in reference_feature_stats.get_all_features():
            description = f"Column {self.column_name} should be in reference data"
            test_result = TestResult.ERROR

        else:
            current_mean = features_stats[self.column_name].mean
            reference_mean = reference_feature_stats[self.column_name].mean
            reference_std = reference_feature_stats[self.column_name].std
            sigmas_value = reference_std * self.n_sigmas
            left_condition = reference_mean - sigmas_value
            right_condition = reference_mean + sigmas_value

            if left_condition < current_mean < right_condition:
                description = (
                    f"The mean value of the column **{self.column_name}** is {current_mean:.3g}."
                    f" The expected range is from {left_condition:.3g} to {right_condition:.3g}"
                )
                test_result = TestResult.SUCCESS

            else:
                description = (
                    f"The mean value of the column **{self.column_name}** is {current_mean:.3g}."
                    f" The expected range is from {left_condition:.3g} to {right_condition:.3g}"
                )
                test_result = TestResult.FAIL

        return TestResult(
            name=self.name,
            description=description,
            status=test_result,
            groups={GroupingTypes.ByFeature.id: self.column_name},
        )


@default_renderer(wrap_type=TestMeanInNSigmas)
class TestMeanInNSigmasRenderer(TestRenderer):
    def render_json(self, obj: TestMeanInNSigmas) -> dict:
        base = super().render_json(obj)
        metric_result = obj.metric.get_result()
        base["parameters"]["column_name"] = obj.column_name
        base["parameters"]["n_sigmas"] = obj.n_sigmas
        base["parameters"]["current_mean"] = metric_result.features_stats[obj.column_name].mean

        if metric_result.reference_features_stats is not None:
            base["parameters"]["reference_mean"] = metric_result.reference_features_stats[obj.column_name].mean
            base["parameters"]["reference_std"] = metric_result.reference_features_stats[obj.column_name].std
        return base

    def render_html(self, obj: TestMeanInNSigmas) -> TestHtmlInfo:
        column_name = obj.column_name
        metric_result = obj.metric.get_result()

        if metric_result.reference_features_stats is not None:
            ref_mean = metric_result.reference_features_stats[column_name].mean
            ref_std = metric_result.reference_features_stats[column_name].std

        else:
            ref_mean = None
            ref_std = None

        if ref_std is None or ref_mean is None:
            raise ValueError("No mean or std for reference")

        gt = ref_mean - obj.n_sigmas * ref_std
        lt = ref_mean + obj.n_sigmas * ref_std
        ref_condition = TestValueCondition(gt=gt, lt=lt)
        info = super().render_html(obj)
        curr_distr = obj.metric.get_result().distr_for_plots[column_name]["current"]
        ref_distr = None

        if "reference" in obj.metric.get_result().distr_for_plots[column_name].keys():
            ref_distr = obj.metric.get_result().distr_for_plots[column_name]["reference"]

        fig = plot_distr(curr_distr, ref_distr)
        fig = plot_check(fig, ref_condition)
        mean_value = obj.metric.get_result().features_stats[column_name].mean

        if mean_value is not None:
            fig = plot_metric_value(fig, mean_value, f"current {column_name} mean value")

        fig_json = fig.to_plotly_json()
        info.details.append(
            DetailsInfo(
                id=f"mean_in_n_sigmas_{column_name}",
                title="",
                info=BaseWidgetInfo(
                    title="",
                    size=2,
                    type="big_graph",
                    params={"data": fig_json["data"], "layout": fig_json["layout"]},
                ),
            )
        )
        return info


class TestNumColumnsMeanInNSigmas(BaseTestGenerator):
    """Create tests of mean for all numeric columns"""

    def generate_tests(self, columns_info: DatasetColumns) -> List[TestMeanInNSigmas]:
        return [TestMeanInNSigmas(column_name=name, n_sigmas=2) for name in columns_info.num_feature_names]


class TestValueRange(Test):
    group = DATA_QUALITY_GROUP.id
    name = "Value Range"
    metric: DataQualityValueRangeMetrics
    column: str
    left: Optional[float]
    right: Optional[float]

    def __init__(
        self,
        column_name: str,
        left: Optional[float] = None,
        right: Optional[float] = None,
        metric: Optional[DataQualityValueRangeMetrics] = None,
    ):
        self.column_name = column_name
        self.left = left
        self.right = right

        if metric is not None:
            self.metric = metric

        else:
            self.metric = DataQualityValueRangeMetrics(column_name=column_name, left=left, right=right)

    def check(self):
        number_not_in_range = self.metric.get_result().number_not_in_range

        if number_not_in_range > 0:
            description = f"The column **{self.column_name}** has values out of range."
            test_result = TestResult.FAIL
        else:
            description = f"All values in the column **{self.column_name}** are within range"
            test_result = TestResult.SUCCESS

        return TestResult(
            name=self.name,
            description=description,
            status=test_result,
            groups={GroupingTypes.ByFeature.id: self.column_name},
        )


@default_renderer(wrap_type=TestValueRange)
class TestValueRangeRenderer(TestRenderer):
    def render_html(self, obj: TestValueRange) -> TestHtmlInfo:
        column_name = obj.column_name
        if obj.left is not None and obj.right is not None:
            condition_ = TestValueCondition(gt=obj.left, lt=obj.right)
        else:
            condition_ = TestValueCondition(gt=obj.metric.get_result().ref_min, lt=obj.metric.get_result().ref_max)
        info = super().render_html(obj)
        curr_distr = obj.metric.get_result().distr_for_plot["current"]
        ref_distr = None
        if "reference" in obj.metric.get_result().distr_for_plot.keys():
            ref_distr = obj.metric.get_result().distr_for_plot["reference"]
        fig = plot_distr(curr_distr, ref_distr)
        fig = plot_check(fig, condition_)

        fig_json = fig.to_plotly_json()
        info.details.append(
            DetailsInfo(
                id=f"value_range_{column_name}",
                title="",
                info=BaseWidgetInfo(
                    title="",
                    size=2,
                    type="big_graph",
                    params={"data": fig_json["data"], "layout": fig_json["layout"]},
                ),
            )
        )
        return info


class BaseDataQualityValueRangeMetricsTest(BaseCheckValueTest, ABC):
    group = DATA_QUALITY_GROUP.id
    metric: DataQualityValueRangeMetrics
    column: str
    left: Optional[float]
    right: Optional[float]

    def __init__(
        self,
        column_name: str,
        left: Optional[float] = None,
        right: Optional[float] = None,
        eq: Optional[Numeric] = None,
        gt: Optional[Numeric] = None,
        gte: Optional[Numeric] = None,
        is_in: Optional[List[Union[Numeric, str, bool]]] = None,
        lt: Optional[Numeric] = None,
        lte: Optional[Numeric] = None,
        not_eq: Optional[Numeric] = None,
        not_in: Optional[List[Union[Numeric, str, bool]]] = None,
        metric: Optional[DataQualityValueRangeMetrics] = None,
    ):
        self.column_name = column_name
        self.left = left
        self.right = right

        if metric is not None:
            self.metric = metric

        else:
            self.metric = DataQualityValueRangeMetrics(column_name=column_name, left=left, right=right)

        super().__init__(eq=eq, gt=gt, gte=gte, is_in=is_in, lt=lt, lte=lte, not_eq=not_eq, not_in=not_in)

    def groups(self) -> Dict[str, str]:
        return {GroupingTypes.ByFeature.id: self.column_name}


class TestNumberOfOutRangeValues(BaseDataQualityValueRangeMetricsTest):
    name = "Number of Out-of-Range Values "

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition
        return TestValueCondition(eq=approx(0))

    def calculate_value_for_test(self) -> Numeric:
        return self.metric.get_result().number_not_in_range

    def get_description(self, value: Numeric) -> str:
        return (
            f"The number of values out of range in the column **{self.column_name}** is {value}. "
            f" The test threshold is {self.get_condition()}."
        )


@default_renderer(wrap_type=TestNumberOfOutRangeValues)
class TestNumberOfOutRangeValuesRenderer(TestRenderer):
    def render_html(self, obj: TestNumberOfOutRangeValues) -> TestHtmlInfo:
        column_name = obj.column_name
        if obj.left is not None and obj.right is not None:
            condition_ = TestValueCondition(gt=obj.left, lt=obj.right)
        else:
            condition_ = TestValueCondition(gt=obj.metric.get_result().ref_min, lt=obj.metric.get_result().ref_max)
        info = super().render_html(obj)
        curr_distr = obj.metric.get_result().distr_for_plot["current"]
        ref_distr = None
        if "reference" in obj.metric.get_result().distr_for_plot.keys():
            ref_distr = obj.metric.get_result().distr_for_plot["reference"]

        fig = plot_distr(curr_distr, ref_distr)
        fig = plot_check(fig, condition_)

        fig_json = fig.to_plotly_json()
        info.details.append(
            DetailsInfo(
                id=f"num_out_of_range_{column_name}",
                title="",
                info=BaseWidgetInfo(
                    title="",
                    size=2,
                    type="big_graph",
                    params={"data": fig_json["data"], "layout": fig_json["layout"]},
                ),
            )
        )
        return info


class TestShareOfOutRangeValues(BaseDataQualityValueRangeMetricsTest):
    name = "Share of Out-of-Range Values"

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition
        return TestValueCondition(eq=approx(0))

    def calculate_value_for_test(self) -> Numeric:
        return self.metric.get_result().share_not_in_range

    def get_description(self, value: Numeric) -> str:
        number_not_in_range = self.metric.get_result().number_not_in_range
        rows_count = self.metric.get_result().rows_count
        return (
            f"The share of values out of range in the column **{self.column_name}** is {value:.3g} "
            f"({number_not_in_range} out of {rows_count}). "
            f" The test threshold is {self.get_condition()}."
        )


@default_renderer(wrap_type=TestShareOfOutRangeValues)
class TestShareOfOutRangeValuesRenderer(TestRenderer):
    def render_json(self, obj: TestShareOfOutRangeValues) -> dict:
        base = super().render_json(obj)
        base["parameters"]["condition"] = obj.get_condition().as_dict()
        base["parameters"]["left"] = obj.left
        base["parameters"]["right"] = obj.right
        base["parameters"]["share_not_in_range"] = obj.value
        return base

    def render_html(self, obj: TestShareOfOutRangeValues) -> TestHtmlInfo:
        column_name = obj.column_name
        if obj.left and obj.right:
            condition_ = TestValueCondition(gt=obj.left, lt=obj.right)
        else:
            condition_ = TestValueCondition(gt=obj.metric.get_result().ref_min, lt=obj.metric.get_result().ref_max)
        info = super().render_html(obj)
        curr_distr = obj.metric.get_result().distr_for_plot["current"]
        ref_distr = None
        if "reference" in obj.metric.get_result().distr_for_plot.keys():
            ref_distr = obj.metric.get_result().distr_for_plot["reference"]
        fig = plot_distr(curr_distr, ref_distr)
        fig = plot_check(fig, condition_)

        fig_json = fig.to_plotly_json()
        info.details.append(
            DetailsInfo(
                id=f"share_out_of_range_{column_name}",
                title="",
                info=BaseWidgetInfo(
                    title="",
                    size=2,
                    type="big_graph",
                    params={"data": fig_json["data"], "layout": fig_json["layout"]},
                ),
            )
        )
        return info


class TestNumColumnsOutOfRangeValues(BaseTestGenerator):
    """Creates share of out of range values tests for all numeric columns"""

    def generate_tests(self, columns_info: DatasetColumns) -> List[TestShareOfOutRangeValues]:
        return [TestShareOfOutRangeValues(column_name=name) for name in columns_info.num_feature_names]


class TestValueList(Test):
    group = DATA_QUALITY_GROUP.id
    name = "Out-of-List Values"
    metric: DataQualityValueListMetrics
    column_name: str
    values: Optional[list]

    def __init__(
        self, column_name: str, values: Optional[list] = None, metric: Optional[DataQualityValueListMetrics] = None
    ):
        self.column_name = column_name
        self.values = values

        if metric is not None:
            self.metric = metric

        else:
            self.metric = DataQualityValueListMetrics(column_name=column_name, values=values)

    def check(self):
        metric_result = self.metric.get_result()

        if metric_result.number_not_in_list > 0:
            test_result = TestResult.FAIL
            description = f"The column **{self.column_name}** has values out of list."

        else:
            test_result = TestResult.SUCCESS
            description = f"All values in the column **{self.column_name}** are in the list."

        return TestResult(
            name=self.name,
            description=description,
            status=test_result,
            groups={GroupingTypes.ByFeature.id: self.column_name},
        )


@default_renderer(wrap_type=TestValueList)
class TestValueListRenderer(TestRenderer):
    def render_json(self, obj: TestValueList) -> dict:
        base = super().render_json(obj)
        base["parameters"]["column_name"] = obj.column_name
        base["parameters"]["values"] = obj.values
        base["parameters"]["number_not_in_list"] = obj.metric.get_result().number_not_in_list
        return base

    def render_html(self, obj: TestValueList) -> TestHtmlInfo:
        info = super().render_html(obj)
        column_name = obj.column_name
        values = obj.values
        curr_df = obj.metric.get_result().counts_of_value["current"]

        if "reference" in obj.metric.get_result().counts_of_value.keys():
            ref_df = obj.metric.get_result().counts_of_value["reference"]

        else:
            ref_df = None

        additional_plots = plot_value_counts_tables(column_name, values, curr_df, ref_df, "value_list")
        info.details = additional_plots
        return info


class BaseDataQualityValueListMetricsTest(BaseCheckValueTest, ABC):
    group = DATA_QUALITY_GROUP.id
    metric: DataQualityValueListMetrics
    column_name: str
    values: Optional[list]

    def __init__(
        self,
        column_name: str,
        values: Optional[list] = None,
        eq: Optional[Numeric] = None,
        gt: Optional[Numeric] = None,
        gte: Optional[Numeric] = None,
        is_in: Optional[List[Union[Numeric, str, bool]]] = None,
        lt: Optional[Numeric] = None,
        lte: Optional[Numeric] = None,
        not_eq: Optional[Numeric] = None,
        not_in: Optional[List[Union[Numeric, str, bool]]] = None,
        metric: Optional[DataQualityValueListMetrics] = None,
    ):
        self.column_name = column_name
        self.values = values

        if metric is not None:
            self.metric = metric

        else:
            self.metric = DataQualityValueListMetrics(column_name=column_name, values=values)

        super().__init__(eq=eq, gt=gt, gte=gte, is_in=is_in, lt=lt, lte=lte, not_eq=not_eq, not_in=not_in)

    def groups(self) -> Dict[str, str]:
        return {GroupingTypes.ByFeature.id: self.column_name}


class TestNumberOfOutListValues(BaseDataQualityValueListMetricsTest):
    name = "Number Out-of-List Values"

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition
        return TestValueCondition(eq=approx(0))

    def calculate_value_for_test(self) -> Numeric:
        return self.metric.get_result().number_not_in_list

    def get_description(self, value: Numeric) -> str:
        return (
            f"The number of values out of list in the column **{self.column_name}** is {value}. "
            f"The test threshold is {self.get_condition()}."
        )


@default_renderer(wrap_type=TestNumberOfOutListValues)
class TestNumberOfOutListValuesRenderer(TestRenderer):
    def render_html(self, obj: TestNumberOfOutListValues) -> TestHtmlInfo:
        info = super().render_html(obj)
        column_name = obj.column_name
        values = obj.values
        curr_df = obj.metric.get_result().counts_of_value["current"]
        ref_df = None
        if "reference" in obj.metric.get_result().counts_of_value.keys():
            ref_df = obj.metric.get_result().counts_of_value["reference"]
        additional_plots = plot_value_counts_tables(column_name, values, curr_df, ref_df, "number_value_list")
        info.details = additional_plots
        return info


class TestShareOfOutListValues(BaseDataQualityValueListMetricsTest):
    name = "Share of Out-of-List Values"

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition
        return TestValueCondition(eq=approx(0))

    def calculate_value_for_test(self) -> Numeric:
        return self.metric.get_result().share_not_in_list

    def get_description(self, value: Numeric) -> str:
        number_not_in_range = self.metric.get_result().number_not_in_list
        rows_count = self.metric.get_result().rows_count
        return (
            f"The share of values out of list in the column **{self.column_name}** is {value:.3g} "
            f"({number_not_in_range} out of {rows_count}). "
            f"The test threshold is {self.get_condition()}."
        )


class TestCatColumnsOutOfListValues(BaseTestGenerator):
    """Create share of out of list values tests for category columns"""

    def generate_tests(self, columns_info: DatasetColumns) -> List[TestShareOfOutListValues]:
        return [TestShareOfOutListValues(column_name=name) for name in columns_info.cat_feature_names]


class TestValueQuantile(BaseCheckValueTest):
    group = DATA_QUALITY_GROUP.id
    name = "Quantile Value"
    metric: DataQualityValueQuantileMetrics
    column_name: str
    quantile: Optional[float]

    def __init__(
        self,
        column_name: str,
        quantile: Optional[float],
        eq: Optional[Numeric] = None,
        gt: Optional[Numeric] = None,
        gte: Optional[Numeric] = None,
        is_in: Optional[List[Union[Numeric, str, bool]]] = None,
        lt: Optional[Numeric] = None,
        lte: Optional[Numeric] = None,
        not_eq: Optional[Numeric] = None,
        not_in: Optional[List[Union[Numeric, str, bool]]] = None,
        metric: Optional[DataQualityValueQuantileMetrics] = None,
    ):
        self.column_name = column_name
        self.quantile = quantile

        if metric is not None:
            if column_name is not None or quantile is not None:
                raise ValueError("Test parameters and given  metric conflict")

            self.metric = metric

        else:
            if quantile is None:
                raise ValueError("Quantile parameter should be present")

            self.metric = DataQualityValueQuantileMetrics(column_name=column_name, quantile=quantile)

        super().__init__(eq=eq, gt=gt, gte=gte, is_in=is_in, lt=lt, lte=lte, not_eq=not_eq, not_in=not_in)

    def groups(self) -> Dict[str, str]:
        return {GroupingTypes.ByFeature.id: self.column_name}

    def get_condition(self) -> TestValueCondition:
        if self.condition.has_condition():
            return self.condition
        ref_value = self.metric.get_result().ref_value
        if ref_value is not None:
            return TestValueCondition(eq=approx(ref_value, 0.1))
        raise ValueError("Neither required test parameters nor reference data has been provided.")

    def calculate_value_for_test(self) -> Numeric:
        return self.metric.get_result().value

    def get_description(self, value: Numeric) -> str:
        return (
            f"The {self.quantile} quantile value of the column **{self.column_name}** is {value:.3g}. "
            f"The test threshold is {self.get_condition()}."
        )


@default_renderer(wrap_type=TestValueQuantile)
class TestValueQuantileRenderer(TestRenderer):
    def render_html(self, obj: TestValueQuantile) -> TestHtmlInfo:
        column_name = obj.column_name
        info = super().render_html(obj)
        curr_distr = obj.metric.get_result().distr_for_plot["current"]
        ref_distr = None
        if "reference" in obj.metric.get_result().distr_for_plot.keys():
            ref_distr = obj.metric.get_result().distr_for_plot["reference"]
        fig = plot_distr(curr_distr, ref_distr)
        fig = plot_check(fig, obj.get_condition())
        fig = plot_metric_value(fig, obj.metric.get_result().value, f"current {column_name} {obj.quantile} quantile")

        fig_json = fig.to_plotly_json()
        info.details.append(
            DetailsInfo(
                id=f"{obj.quantile}_quantile_{column_name}",
                title="",
                info=BaseWidgetInfo(
                    title="",
                    size=2,
                    type="big_graph",
                    params={"data": fig_json["data"], "layout": fig_json["layout"]},
                ),
            )
        )
        return info


@default_renderer(wrap_type=TestShareOfOutListValues)
class TestShareOfOutListValuesRenderer(TestRenderer):
    def render_json(self, obj: TestShareOfOutListValues) -> dict:
        base = super().render_json(obj)
        base["parameters"]["condition"] = obj.get_condition().as_dict()
        base["parameters"]["values"] = obj.values
        base["parameters"]["share_not_in_list"] = obj.value
        return base

    def render_html(self, obj: TestShareOfOutListValues) -> TestHtmlInfo:
        info = super().render_html(obj)
        column_name = obj.column_name
        values = obj.values
        curr_df = obj.metric.get_result().counts_of_value["current"]
        ref_df = None
        if "reference" in obj.metric.get_result().counts_of_value.keys():
            ref_df = obj.metric.get_result().counts_of_value["reference"]
        additional_plots = plot_value_counts_tables(column_name, values, curr_df, ref_df, "share_value_list")
        info.details = additional_plots
        return info
