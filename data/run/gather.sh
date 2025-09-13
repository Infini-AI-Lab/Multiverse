# BEFORE RUN THIS SCRIPT, YOU NEED TO SET THE ROOT_DIR

cd $root_dir/data

echo "================================================"
echo "Afterwards..."
python afterwards.py \
    --input_file_path $root_dir/data/output/step3/parse \
    --output_file_path $root_dir/data/output/step3/afterwards/

echo "================================================"
echo "Calculating distance..."
python distance.py \
    --input_file_path $root_dir/data/1.1k.jsonl \
    --output_file_path $root_dir/data/1.1k_multiverse.jsonl \
    --reasoning_dir $root_dir/data/output/step3/parse/ \
    --afterwards_dir $root_dir/data/output/step3/afterwards/ \
    --pattern s1 \
    --threshold 0.9 # Very high for testing