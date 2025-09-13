# BEFORE RUN THIS SCRIPT, YOU NEED TO SET THE ROOT_DIR and GOOGLE_API_KEY

export GOOGLE_API_KEY=YOUR_GOOGLE_API_KEY

cd $root_dir/data/
python gemini.py \
    --prompt $root_dir/data/prompt/step2-prompt.txt \
    --input $root_dir/data/1.1k.jsonl \
    --output $root_dir/data/output/step2/ \
    --chat $root_dir/data/output/step2/chat \
    --structure $root_dir/data/output/step1/ \
    --start_idx 1 \
    --end_idx 2