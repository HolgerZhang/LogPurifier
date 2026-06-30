## HDFS_v1
HDFS (http://hadoop.apache.org/hdfs) is the Hadoop Distributed File System designed to run on commodity hardware. Due to the popularity of HDFS, it has been widely studied in the literature. 

This log set is generated in a private cloud environment using benchmark workloads, and manually labeled through handcrafted rules to identify the anomalies. The logs are sliced into traces according to block ids. Then each trace associated with a specific block id is assigned a groundtruth label: normal/anomaly. 

### Download
The raw logs are available for downloading at https://github.com/logpai/loghub. Direct download link: https://zenodo.org/records/8196385/files/HDFS_v1.zip?download=1

Decompress and place `HDFS.log` and `anomaly_label.csv` at `data/HDFS/HDFS.log` and `data/HDFS/anomaly_label.csv`.

### Citation
If you use the HDFS_v1 dataset from loghub in your research, please cite the following papers.
+ Wei Xu, Ling Huang, Armando Fox, David Patterson, Michael Jordan. [Detecting Large-Scale System Problems by Mining Console Logs](https://people.eecs.berkeley.edu/~jordan/papers/xu-etal-sosp09.pdf), in Proc. of the 22nd ACM Symposium on Operating Systems Principles (SOSP), 2009.
+ Jieming Zhu, Shilin He, Pinjia He, Jinyang Liu, Michael R. Lyu. [Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics](https://arxiv.org/abs/2008.06448). IEEE International Symposium on Software Reliability Engineering (ISSRE), 2023.
