# BEFORE RUN THIS SCRIPT, YOU NEED TO SET THE ROOT_DIR

cd $root_dir/data/
echo "================================================"
echo "Preprocessing..."
python preprocess.py \
    --input_dir_path $root_dir/data/output/step2/ \
    --output_dir_path $root_dir/data/output/step2/process/ \
    --ref_path $root_dir/data/1.1k.jsonl \
    --pattern s1

echo "================================================"
echo "Parsing..."
python parse.py \
    --input_file_path $root_dir/data/output/step2/process/ \
    --output_file_path $root_dir/data/output/step2/parse/ \
    --pattern s1


