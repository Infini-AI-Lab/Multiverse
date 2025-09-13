# BEFORE RUN THIS SCRIPT, YOU NEED TO SET THE ROOT_DIR

export GOOGLE_API_KEY=YOUR_GOOGLE_API_KEY

cd $root_dir/data/
python refill_block.py \
    --input $root_dir/data/1.1k.jsonl \
    --output_xml $root_dir/data/output/step3/parse \
    --xml_path $root_dir/data/output/step2/parse \
    --prompt $root_dir/data/prompt/step3-prompt.txt \
    --start_idx 0 \
    --end_idx 1000