# Source on the Framework before an eval: loads the model servers' bearer tokens.
#   . scripts/framework_env.sh
set -a
. ~/.config/s1doom/laya-serve.env
. ~/semif/semif-serve.env
. ~/clef/clef-serve.env
set +a
