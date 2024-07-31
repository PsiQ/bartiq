FROM python:3.11

ARG TARGET_DIR=/bartiq

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      graphviz=2.* \
      git=1:2.* \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

USER $USERNAME

ENV PATH="/home/$USERNAME/.local/bin:$PATH"

RUN pip install --user poetry~=1.8.3

WORKDIR $TARGET_DIR

COPY . .

# Allow mkdocs to use the .git folder for git-plugins which is owned by the host
RUN git config --global --add safe.directory $TARGET_DIR \
    && poetry config virtualenvs.in-project true \
    && poetry install --all-extras --no-cache

ENV PATH="$TARGET_DIR/.venv/bin:$PATH"
