""" Analysis module for all kinds of experiments
"""

import os
import sys

import hydra
import numpy as np
import pandas as pd
from crates.helpers import target_statistics
from feature_corr.stations.verifications import VerifyFeatures
from loguru import logger
from omegaconf import DictConfig
from sklearn.model_selection import train_test_split

from feature_corr.utils.exploration import ExploreData

# pd.set_option('display.max_rows', None)
# pd.set_option('display.max_columns', None)
# pd.set_option('display.width', None)
# pd.set_option('display.max_colwidth', None)


class Analysis:
    def __init__(self, config: DictConfig) -> None:
        self.config = config
        self.src_dir = config.dataset.out_dir
        self.impute = config.merge.impute
        self.overwrite = config.merge.overwrite
        self.experiment_name = config.analysis.experiment.name
        self.target_label = config.analysis.experiment.target_label
        self.explore_frac = config.analysis.run.verification.explore_frac
        self.seed = config.analysis.run.seed
        np.random.seed(self.seed)

    def __call__(self) -> None:
        new_name = f'{self.experiment_name}_imputed' if self.impute else self.experiment_name
        merged_path = os.path.join(self.src_dir, '5_merged', f'{new_name}.xlsx')
        self.config.analysis.experiment.name = new_name

        data = pd.read_excel(merged_path)  # Read in merged data
        data = data.set_index('subject')  # Use subject ID as index column
        task, stratify = target_statistics(data, self.target_label)

        if 0 < self.explore_frac < 1:
            explore_data, verification_data = train_test_split(
                data, stratify=stratify, test_size=1 - self.explore_frac, random_state=self.seed
            )
            verification_data_test = None
        elif self.explore_frac == 0:  # special mode in which entire train data is used for exploration and verification
            verification_data, verification_data_test = train_test_split(
                data, stratify=stratify, test_size=0.2, random_state=self.seed
            )
            explore_data = verification_data
        else:
            raise ValueError(f'Value {self.explore_frac} is invalid, must be float in (0, 1)')

        explorer = ExploreData(self.config, explore_data, task)
        features = explorer()

        verify = VerifyFeatures(self.config, verification_data, verification_data_test, features, task)
        verify()


if __name__ == '__main__':

    @hydra.main(version_base=None, config_path='../../config', config_name='config')
    def main(config: DictConfig) -> None:
        logger.remove()
        logger.add(sys.stderr, level=config.logging_level)
        analysis = Analysis(config)
        analysis()

    main()