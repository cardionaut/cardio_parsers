import os

import pandas as pd
from crates.normalisers import Normalisers
from loguru import logger
from omegaconf import DictConfig

from feature_corr.crates.selections.dim_reductions import DimensionReductions
from feature_corr.crates.selections.feature_reductions import FeatureReductions
from feature_corr.crates.selections.recursive_feature_elimination import (
    RecursiveFeatureElimination,
)
from feature_corr.data_borg import DataBorg


class Selection(DataBorg, Normalisers, DimensionReductions, FeatureReductions, RecursiveFeatureElimination):
    """Execute jobs"""

    def __init__(self, config: DictConfig) -> None:
        super().__init__()
        self.config = config

        self.seed = config.meta.seed
        self.jobs = config.selection.jobs
        self.task = config.meta.learn_task
        self.out_dir = config.meta.output_dir
        self.scoring = config.selection.scoring
        self.experiment_name = config.meta.name
        self.state_name = config.meta.state_name
        self.target_label = config.meta.target_label
        self.corr_method = config.selection.corr_method
        self.corr_thresh = config.selection.corr_thresh
        self.class_weight = config.selection.class_weight
        self.variance_thresh = config.selection.variance_thresh
        self.auto_norm_method = config.selection.auto_norm_method
        self.keep_top_features = config.selection.keep_top_features
        self.corr_drop_features = config.selection.corr_drop_features
        self.job_name = ''
        self.job_dir = None

    def __call__(self) -> None:
        """Run all jobs"""
        self.__check_jobs()
        self.__check_auto_norm_methods()

        for job in self.jobs:
            logger.info(f'Running -> {job}')
            self.job_name = '_'.join(job)  # name of current job
            self.job_dir = os.path.join(self.out_dir, self.experiment_name, self.state_name, self.job_name)
            os.makedirs(self.job_dir, exist_ok=True)
            frame = self.get_store('frame', self.state_name, 'selection_train')
            for step in job:
                logger.trace(f'Running -> {step}')
                frame, features, error = self.process_job(step, frame)
                if error:
                    logger.error(f'Step {step} is invalid')
                    break
                self.__store_features(features)

    def __check_jobs(self) -> None:
        """Check if the given jobs are valid"""
        valid_methods = set([x for x in dir(self) if not x.startswith('_') and x != 'process_job'])
        jobs = set([x for sublist in self.jobs for x in sublist])
        if not jobs.issubset(valid_methods):
            raise ValueError(f'Invalid job, check -> {str(jobs - valid_methods)}')

    def __check_auto_norm_methods(self) -> None:
        """Check if auto_norm_method keys are valid"""
        valid_methods = set([x for x in dir(self) if not x.startswith('_') and x.endswith('norm')])
        selected_methods = set(self.auto_norm_method.values())
        if not selected_methods.issubset(valid_methods):
            raise ValueError(f'Invalid auto norm method, check -> {str(selected_methods - valid_methods)}')

    def __store_features(self, features: list) -> None:
        """Store features"""
        if features:
            if isinstance(features, list):
                if len(features) > 0:
                    logger.info('Found top features')
                    self.set_store('feature', self.state_name, self.job_name, features)
                else:
                    logger.warning(f'No features found for {self.job_name}')
            else:
                logger.warning('Selected features are not a list')

    def process_job(self, step: str, frame: pd.DataFrame) -> tuple:
        """Process data according to the given step"""
        if frame is None:
            logger.warning(
                f'No data available for step: {step} in {self.job_name}. '
                f'\nThe previous step does not seem to produce any output.'
            )
            return None, None, True
        frame, features = getattr(self, step)(frame)
        return frame, features, False