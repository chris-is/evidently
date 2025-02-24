from evidently.utils.data_operations import DatasetColumns
from evidently.metrics.base_metric import InputData
from evidently.metric_preset.metric_preset import MetricPreset
from evidently.metrics.data_quality_metrics import DataQualityMetrics


class DataQuality(MetricPreset):
    def generate_metrics(self, data: InputData, columns: DatasetColumns):
        return [DataQualityMetrics()]
