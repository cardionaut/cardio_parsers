""" Analysis module for all kinds of experiments
"""

import os
import re
import sys

import hydra
import numpy as np
import pandas as pd
from loguru import logger
from omegaconf import DictConfig
from sklearn.experimental import enable_iterative_imputer  # because of bug in sklearn
from sklearn.impute import IterativeImputer, KNNImputer, MissingIndicator, SimpleImputer
from sklearn.model_selection import train_test_split

from excel.analysis.utils.exploration import ExploreData
from excel.analysis.utils.helpers import target_statistics
from excel.analysis.utils.merge_data import MergeData
from excel.analysis.verifications import VerifyFeatures

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

        # Data merging
        if os.path.isfile(merged_path) and not self.overwrite:
            logger.info('Merged data available, skipping merge step...')
        else:
            merger = MergeData(self.config)
            merger()

        data = pd.read_excel(merged_path)  # Read in merged data
        data = data.set_index('ATTRAS_Redcap')  # Use subject ID as index column
        task, stratify = target_statistics(data, self.target_label)
        self.config.analysis.run.scoring = self.config.analysis.run.scoring[task]

        # ATTRAS-specific imputation
        reg = re.compile('([A-Za-z]+(_[A-Za-z]+)+)_[0-9]+')
        single_seg_cols = list(filter(reg.match, data.columns))
        logger.debug(single_seg_cols)
        data = data.drop(single_seg_cols, axis=1)
        data = data.apply(pd.to_numeric, errors='coerce')
        nunique = data.nunique()
        non_binary_cols = nunique[nunique != 2].index
        data[non_binary_cols] = data[non_binary_cols].replace(0, np.nan)
        imputer = IterativeImputer(
            initial_strategy='median',
            max_iter=100,
            random_state=self.seed,
            keep_empty_features=True,
        )
        imp_data = imputer.fit_transform(data)
        data = pd.DataFrame(imp_data, index=data.index, columns=data.columns)

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
