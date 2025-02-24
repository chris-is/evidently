from evidently.utils.data_operations import DatasetColumns
from evidently.metrics.base_metric import InputData
from evidently.metric_preset.metric_preset import MetricPreset
from evidently.metrics.num_target_drift_metrics import NumTargetDriftMetrics


class NumTargetDrift(MetricPreset):
    def generate_metrics(self, data: InputData, columns: DatasetColumns):
        return [NumTargetDriftMetrics()]
