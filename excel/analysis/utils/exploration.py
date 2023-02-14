"""Data exploration module
"""

import os
from copy import deepcopy

from loguru import logger
import pandas as pd
from omegaconf import DictConfig

from excel.analysis.utils import analyse_variables
from excel.analysis.utils import dim_reduction
from excel.analysis.utils.helpers import variance_threshold
from excel.analysis.utils.normalisers import Normaliser
from excel.analysis.utils.dim_reduction import DimensionReductions
from excel.analysis.utils.analyse_variables import AnalyseVariables


from types import FunctionType


class ExploreData(Normaliser, DimensionReductions, AnalyseVariables):
    def __init__(self, data: pd.DataFrame, config: DictConfig) -> None:
        super().__init__()
        self.original_data = data
        self.out_dir = os.path.join(config.dataset.out_dir, '6_exploration', config.analysis.experiment.name)
        self.jobs = config.analysis.run.jobs
        self.seed = config.analysis.run.seed
        self.corr_thresh = config.analysis.run.corr_thresh
        self.variance_thresh = config.analysis.run.variance_thresh
        self.metadata = config.analysis.experiment.metadata
        self.target_label = config.analysis.experiment.target_label

        self.job_name = ''

    def __call__(self) -> None:
        for job in self.jobs:
            logger.info(f'Running {job}')
            self.job_name = '_'.join(job)  # name of current job
            self.job_dir = os.path.join(self.out_dir, self.job_name)
            os.makedirs(self.job_dir, exist_ok=True)
            data = deepcopy(self.original_data)
            for step in job:
                data, error = self.process_job(step, data)
                if error:
                    break

    @classmethod
    def get_member_methods(cls):
        """Return a list of all methods of the class"""
        all_methods = [x for x, y in cls.__dict__.items() if type(y) == FunctionType]
        return [x for x in all_methods if not x.startswith('_') and x != 'process_job']

    def process_job(self, step, data):
        """Process data according to the given step"""
        if hasattr(self, step):
            if data is None:
                logger.warning(
                    f'No data available for step: {step} in {self.job_name}. '
                    f'\nThe previous step does not seem to produce any output.'
                )
                return None, True
            # try:
            data = getattr(self, step)(data)
            # except:
            #     logger.warning(f'Error in step: {step} in {self.job_name}.')
            return data, False
        # raise logger.error(f'Invalid step name: "{step}",\nvalid step names: {self.get_member_methods()}')



    def variance_threshold(self, data):
        """Perform variance threshold based feature selection on the data"""
        data = variance_threshold(
            data=data,
            label=self.target_label,
            thresh=self.variance_thresh,
        )
        return data

