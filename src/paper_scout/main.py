# main.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

import argparse
import logging
import sys
from pathlib import Path

from paper_scout.core.constant import DEFAULT_PACKAGE_NAME
from paper_scout.core.logger import set_global_logger
from paper_scout.pipeline import Pipeline


# 获取日志记录器
logger = logging.getLogger(f"{DEFAULT_PACKAGE_NAME}.main")


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="PaperScout CLI")
    parser.add_argument("--start-year", "-s", type=int, required=True,
                        help="Start year for fetching papers")
    parser.add_argument("--end-year", "-e", type=int, required=True,
                        help="End year for fetching papers")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-all", "-a", action="store_true",
                       help="Run complete workflow")
    group.add_argument("--stage", choices=["fetch", "parse", "analyze", "filter", "upload"],
                       help="Run specified stage")
    parser.add_argument("--log-directory", type=Path, default=Path("logs"),
                        help="Directory to store log files")
    parser.add_argument("--log-level", type=str.upper, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Set the logging level")
    args = parser.parse_args()
    # 设置全局日志记录
    set_global_logger(
        log_directory=args.log_directory, log_level=args.log_level, root_name=DEFAULT_PACKAGE_NAME)
    # 记录启动信息
    logger.info("=" * 50)
    logger.info(f"PaperScout started!")
    logger.info(f"Arguments: {vars(args)}")
    print("=" * 50)
    print("\nPaperScout started!\n")
    # 创建工作流程
    pipeline = Pipeline(start_year=args.start_year, end_year=args.end_year)
    # 执行指定阶段或完整工作流程
    try:
        if args.run_all:
            pipeline.run_all()
        elif args.stage == "fetch":
            pipeline.run_fetch_stage()
        elif args.stage == "parse":
            pipeline.run_parse_stage()
        elif args.stage == "analyze":
            pipeline.run_analyze_stage()
        elif args.stage == "filter":
            pipeline.run_filter_stage(refilter=True)
        elif args.stage == "upload":
            pipeline.run_upload_stage()
        else:
            parser.print_help()
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}")
        print(f"[CRITICAL] An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
