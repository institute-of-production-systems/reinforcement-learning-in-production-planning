import gymnasium as gym
from .task_envs.task_envs_list import register_environment, get_all_registered_envs


def load_environment(id, production_system, max_episode_steps=10000, register_only=False):
    """
    Registers the TaskEnvironment wanted, if it exists in the Task_Envs.

    Checks that the workspace of the user has all that is needed for launching this.
    """
    print("Env: {} will be imported".format(id))
    result = None
    if id not in get_all_registered_envs():
        result = register_environment(
                task_env=id,
                max_episode_steps=max_episode_steps,
                production_system=production_system
            )
    else:
        result = True
    
    if register_only:
        return

    if result:
        print("Register of Task Env went OK, lets make the env..." +
                      str(id))
        env = gym.make(id)
    else:
        print("Something Went wrong in the register")
        env = None

    return env
