import sys
import json
import argparse
import os

from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3 import PPO
from stable_baselines3.common.evaluation import evaluate_policy
from stable_baselines3.common.callbacks import EvalCallback
from stable_baselines3.common.vec_env.dummy_vec_env import DummyVecEnv
from stable_baselines3.common.vec_env.vec_video_recorder import VecVideoRecorder

from torch import nn as nn
from typing import Dict, Any

n_evaluations = 20
n_envs = 1
n_timesteps = 1e6

parser = argparse.ArgumentParser()
parser.add_argument("--study-name", help="Study name used during hyperparameter optimization", type=str, default=None)
parser.add_argument("--env-name", help="Env to use during hyperaparameter evaluation", type=str, default=None)
args = parser.parse_args()

study_dir = './mujoco_hyperparameters/' + args.study_name
for param_id in range(2):
    param_file = study_dir + "/hyperparameters_" + str(param_id) + ".json"
    with open(param_file) as f:
        params = json.load(f)

    # Fix "use_pybullet_params"
    policy_kwargs = dict(
        log_std_init=-2,
        ortho_init=False,
        activation_fn=nn.ReLU,
        net_arch=[dict(pi=[256, 256], vf=[256, 256])]
    ) if params['use_pybullet_params'] else None

    params.pop('use_pybullet_params')
    params['policy_kwargs'] = policy_kwargs
        
    print("Evaluating Hyperparameters...")
    print(params)

    # No normalization, frame stacking, or image space transformation is required
    env = make_vec_env(env_id=args.env_name,
                        n_envs=n_envs,
                        wrapper_class=None,
                        monitor_dir=None,
                        env_kwargs=None,
                        vec_env_cls=DummyVecEnv,
                        vec_env_kwargs=None,
                        monitor_kwargs=None)

    eval_env = make_vec_env(env_id=args.env_name,
                        n_envs=n_envs,
                        wrapper_class=None,
                        monitor_dir=None,
                        env_kwargs=None,
                        vec_env_cls=DummyVecEnv,
                        vec_env_kwargs=None,
                        monitor_kwargs=None)
    eval_freq = int(n_timesteps / n_evaluations)

    all_mean_rewards = []
    eval_log_dir = study_dir + '/eval_logs/' + str(param_id) + '/'
    os.makedirs(eval_log_dir, exist_ok=True)

    eval_log_file = eval_log_dir + 'reward_stat.txt'
    with open(eval_log_file, "w+") as f:
        for i in range(10):
            model = PPO('MlpPolicy', env, verbose=0, **params)
            eval_callback = EvalCallback(eval_env, best_model_save_path=eval_log_dir, log_path=eval_log_dir, eval_freq=eval_freq, deterministic=True, render=False)
            model.learn(total_timesteps=n_timesteps, callback=eval_callback)
            model = PPO.load(eval_log_dir + '/best_model')
            mean_reward, std_reward = evaluate_policy(model, eval_env, deterministic=True, n_eval_episodes=25)
            
            log = str(i) + "th mean reward:" + str(mean_reward) + " / std reward:" + str(std_reward)
            print(log)
            f.write(log)
            f.write('\n')
            all_mean_rewards.append(mean_reward)
        
        total_mean_reward = sum(all_mean_rewards) / len(all_mean_rewards)
        log = "Total mean reward:" + str(total_mean_reward)
        print(log)
        f.write(log)

        if param_id == 0:
            best_param = params
            best_param_id = param_id
            best_total_mean_reward = total_mean_reward
        else:
            if total_mean_reward > best_total_mean_reward:
                best_param = params
                best_param_id = param_id
                best_total_mean_reward = total_mean_reward

best_param_dir = study_dir + '/eval_logs/best'
os.makedirs(best_param_dir, exist_ok=True)

# Best params
best_param_file = best_param_dir + '/best_hyperparameters.json'
if best_param['policy_kwargs'] is not None:
    best_param['policy_kwargs'] = "dict(log_std_init=-2, ortho_init=False, activation_fn=nn.ReLU, net_arch=[dict(pi=[256, 256], vf=[256, 256])]"

text = json.dumps(best_param)
with open(best_param_file, "w") as jsonFile:
    jsonFile.write(text)
    
# Record
env = make_vec_env(env_id=args.env_name,
                    n_envs=1,
                    wrapper_class=None,
                    monitor_dir=None,
                    env_kwargs=None,
                    vec_env_cls=DummyVecEnv,
                    vec_env_kwargs=None,
                    monitor_kwargs=None)
obs = env.reset()
video_length = int(1e10)
    
env = VecVideoRecorder(env, best_param_dir, record_video_trigger=lambda x: x == 0, video_length=video_length)
env.reset()

best_eval_log_dir = study_dir + '/eval_logs/' + str(best_param_id) + '/'
model = PPO.load(best_eval_log_dir + '/best_model')
for _ in range(video_length + 1):
    action = model.predict(obs, deterministic=True)
    obs, _, done, _ = env.step(action)
    if done:
        break
env.close()

# env = pistonball_v4.parallel_env()
# env = ss.color_reduction_v0(env, mode='B')
# env = ss.resize_v0(env, x_size=84, y_size=84)
# env = ss.frame_stack_v1(env, 3)
# env = ss.pettingzoo_env_to_vec_env_v0(env)
# env = ss.concat_vec_envs_v0(env, n_envs, num_cpus=1, base_class='stable_baselines3')
# env = VecMonitor(env)
# env = image_transpose(env)

# eval_env = pistonball_v4.parallel_env()
# eval_env = ss.color_reduction_v0(eval_env, mode='B')
# eval_env = ss.resize_v0(eval_env, x_size=84, y_size=84)
# eval_env = ss.frame_stack_v1(eval_env, 3)
# eval_env = ss.pettingzoo_env_to_vec_env_v0(eval_env)
# eval_env = ss.concat_vec_envs_v0(eval_env, 1, num_cpus=1, base_class='stable_baselines3')
# eval_env = VecMonitor(eval_env)
# eval_env = image_transpose(eval_env)

# eval_freq = int(n_timesteps / n_evaluations)
# eval_freq = max(eval_freq // (n_envs * n_agents), 1)

# all_mean_rewards = []
# for i in range(10):
#     model = PPO("CnnPolicy", env, verbose=3, **params)
#     eval_callback = EvalCallback(eval_env, best_model_save_path='./eval_logs/' + num + '/', log_path='./eval_logs/' + num + '/' , eval_freq=eval_freq, deterministic=True, render=False)
#     model.learn(total_timesteps=n_timesteps, callback=eval_callback) 
#     model = PPO.load('./eval_logs/' + num + '/' + 'best_model')
#     mean_reward, std_reward = evaluate_policy(model, eval_env, deterministic=True, n_eval_episodes=25)
#     print(mean_reward)
#     print(std_reward)
#     all_mean_rewards.append(mean_reward)
#     if mean_reward > 90:
#         model.save('./mature_policies/' + str(num) + '/' + str(i) + '/')


# print(sum(all_mean_rewards) / len(all_mean_rewards))